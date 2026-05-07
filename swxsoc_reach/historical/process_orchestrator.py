"""Per-day orchestrator for historical CSV \u2192 CDF processing.

Drives :func:`swxsoc_reach.calibration.calibration.process_file` over
an inclusive UTC date range, picking up CSVs produced by Phase 1's
download orchestrator from ``--input-dir``. Each day produces one
CDF in ``--output-dir`` and (optionally) one S3 upload via
:func:`swxsoc_reach.historical.s3_upload.upload_cdf_to_s3`. Telemetry
is appended to the same CSV file Phase 1 wrote (extended schema), so
the full download \u2192 process \u2192 upload lifecycle for a given day is
visible in one place.

Sequential by day, mirroring the download orchestrator. The
chdir-into-output-dir hack is required because
``process_file`` writes to ``Path.cwd()`` when ``LAMBDA_ENVIRONMENT``
is unset (which is the case for historical local runs); we restore
``cwd`` in ``finally`` so a failure mid-day does not leave the
process in a bad state.
"""

from __future__ import annotations

import os
import shutil
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from swxsoc_reach import log
from swxsoc_reach.historical._dates import iter_dates as _iter_dates
from swxsoc_reach.historical.telemetry import (
    HistoricalTelemetry,
    STATUS_DOWNLOAD_PENDING,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_PROCESS_PENDING,
    STATUS_PROCESSED,
    STATUS_SKIPPED_NO_DATA,
    STATUS_SKIPPED_NO_INPUT,
    STATUS_UPLOAD_PENDING,
    STATUS_UPLOADED,
    TelemetryRow,
    utcnow_iso,
)

# Lazy: imported only when needed, to keep ``process_orchestrator``
# importable on machines without the calibration stack ready.


@dataclass
class ProcessRunConfig:
    """Inputs to :func:`run_process`.

    Mirrors the historical-process CLI flags one-for-one. The CLI
    layer parses argv into one of these instances.

    Fields
    ------
    - ``start_date``, ``end_date`` : inclusive UTC date range.
    - ``input_dir`` : directory holding Phase 1 download artifacts
      (CSV/JSON files named per
      :func:`~swxsoc_reach.net.udl.build_reach_output_filename`).
    - ``output_dir`` : directory where CDF files are written.
    - ``telemetry_path`` : append-only telemetry CSV (typically the
      same file Phase 1 wrote).
    - ``sensor_id``, ``descriptor``, ``output_format`` : used to
      reconstruct the expected per-day input filename when scanning
      ``input_dir``.
    - ``retry_failed`` : when True, days with prior status ``FAILED``
      are re-attempted.
    - ``limit_days`` : cap on attempted days (counted from the first
      not-yet-complete day).
    - ``dry_run`` : plan only - no work, no telemetry writes.
    - ``upload_to_s3`` : if True, attempt an S3 upload after a
      successful CDF write. If False, ``PROCESSED`` is the terminal
      status for the day.
    - ``s3_bucket`` : destination bucket (required iff
      ``upload_to_s3`` is True).
    """

    start_date: date
    end_date: date
    input_dir: Path
    output_dir: Path
    telemetry_path: Path
    sensor_id: str = "ALL"
    descriptor: str = "QUICKLOOK"
    output_format: str = "csv"
    retry_failed: bool = False
    limit_days: int | None = None
    dry_run: bool = False
    upload_to_s3: bool = False
    s3_bucket: str | None = None


@dataclass
class ProcessRunSummary:
    """Aggregate result of one :func:`run_process` invocation."""

    run_id: str
    days_planned: int
    days_attempted: int
    days_processed: int
    days_uploaded: int
    days_skipped_existing: int
    days_skipped_no_input: int
    days_failed: int


def _match_csv_for_date(
    input_dir: Path,
    day: date,
    sensor_id: str,
    output_format: str,
) -> Path | None:
    """Return the per-day input artifact path or ``None`` if missing.

    Phase 1 names files via
    :func:`~swxsoc_reach.net.udl.build_reach_output_filename`:
    ``{sensor_prefix}_{startTIME}_{endTIME}.{output_format}`` where
    the time format is ``%Y%m%dT%H%M%S``. For a UTC day, the start
    component is ``YYYYMMDDT000000`` and the end is the next day's
    ``YYYYMMDDT000000``. We glob loosely on the leading sensor +
    start-time prefix so any pair of matching start/end timestamps is
    accepted.
    """
    sensor_prefix = "REACH-ALL" if sensor_id.upper() == "ALL" else sensor_id
    start_str = day.strftime("%Y%m%dT000000")
    pattern = f"{sensor_prefix}_{start_str}_*.{output_format}"
    matches = sorted(input_dir.glob(pattern))
    if not matches:
        return None
    if len(matches) > 1:
        log.warning(
            f"{day.isoformat()}: multiple input files match {pattern!r} in "
            f"{input_dir}; using {matches[0].name}"
        )
    return matches[0]


def _decide_process_action(
    prior: TelemetryRow | None,
    *,
    upload_to_s3: bool,
    csv_available: bool,
    retry_failed: bool,
) -> str:
    """Return one of:

    - ``run_process``: (re)run process_file from CSV (and upload if configured)
    - ``run_upload_only``: CDF already exists; just upload
    - ``skip_existing``: day already terminal; nothing to do
    - ``skip_terminal``: prior SKIPPED_NO_INPUT and CSV still missing
    - ``skip_failed``: prior FAILED and ``--retry-failed`` not set
    """
    if prior is None:
        return "run_process" if csv_available else "skip_no_input"

    status = prior.status

    if status == STATUS_UPLOADED:
        return "skip_existing"

    if status == STATUS_PROCESSED:
        cdf = prior.cdf_path
        cdf_exists = bool(cdf) and Path(cdf).exists()
        if upload_to_s3:
            if cdf_exists:
                return "run_upload_only"
            return "run_process" if csv_available else "skip_no_input"
        # local-only mode: PROCESSED is terminal
        if cdf_exists:
            return "skip_existing"
        return "run_process" if csv_available else "skip_no_input"

    if status == STATUS_UPLOAD_PENDING:
        cdf = prior.cdf_path
        if cdf and Path(cdf).exists():
            return "run_upload_only"
        return "run_process" if csv_available else "skip_no_input"

    if status == STATUS_PROCESS_PENDING:
        return "run_process" if csv_available else "skip_no_input"

    if status == STATUS_FAILED:
        if not retry_failed:
            return "skip_failed"
        return "run_process" if csv_available else "skip_no_input"

    if status == STATUS_SKIPPED_NO_INPUT:
        return "run_process" if csv_available else "skip_terminal"

    # Phase 1 statuses (DOWNLOAD_PENDING / DOWNLOADED / SKIPPED_NO_DATA):
    # treat as no prior process-stage row.
    if status in (STATUS_DOWNLOAD_PENDING, STATUS_DOWNLOADED, STATUS_SKIPPED_NO_DATA):
        return "run_process" if csv_available else "skip_no_input"

    # Unknown status \u2192 attempt to process if we have an input.
    return "run_process" if csv_available else "skip_no_input"


def _carry_forward(prior: TelemetryRow | None) -> dict[str, str]:
    """Carry Phase 1 download columns forward onto a Phase 2 row.

    Keeps the most-recent row per day self-describing in the telemetry
    CSV. When no prior row exists, returns blank values so column
    positions are populated.
    """
    if prior is None:
        return {
            "records_downloaded": "",
            "expected_records": "",
            "availability_pct": "",
            "download_seconds": "",
            "csv_size_mb": "",
            "csv_path": "",
        }
    return {
        "records_downloaded": prior.records_downloaded,
        "expected_records": prior.expected_records,
        "availability_pct": prior.availability_pct,
        "download_seconds": prior.download_seconds,
        "csv_size_mb": prior.csv_size_mb,
        "csv_path": prior.csv_path,
    }


def _process_one_day(
    csv_path: Path,
    output_dir: Path,
    process_fn: Callable[[Path], list[Path]],
) -> list[Path]:
    """Run ``process_file(csv_path)`` with cwd switched to ``output_dir``.

    ``process_file`` writes to ``Path.cwd()`` when ``LAMBDA_ENVIRONMENT``
    is unset, so we chdir for the duration of the call and restore in
    ``finally``. Sequential per-day execution makes this safe.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_cwd = os.getcwd()
    try:
        os.chdir(output_dir)
        return list(process_fn(csv_path))
    finally:
        os.chdir(saved_cwd)


def _relocate_to_nested_layout(flat_path: Path, output_dir: Path) -> Path:
    """Move *flat_path* into a nested subdirectory of *output_dir*.

    The subdirectory mirrors the S3 key produced by
    :func:`sdc_aws_utils.aws.create_s3_file_key` (e.g.
    ``l1c/prelim/2026/01/01/``). Falls back to returning *flat_path*
    unchanged if ``sdc_aws_utils`` or ``swxsoc`` are not importable, or
    if key computation raises for any reason.
    """
    try:
        from sdc_aws_utils.aws import create_s3_file_key
        from swxsoc.util.util import parse_science_filename
    except ImportError:
        log.debug(
            f"_relocate_to_nested_layout: sdc_aws_utils/swxsoc not available; "
            f"keeping flat layout for {flat_path.name!r}"
        )
        return flat_path

    try:
        nested_key = create_s3_file_key(parse_science_filename, flat_path.name)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            f"Could not compute nested layout key for {flat_path.name!r}; "
            f"keeping flat ({type(exc).__name__}: {exc})"
        )
        return flat_path

    dest = output_dir / nested_key
    if dest.resolve() == flat_path.resolve():
        return flat_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(flat_path), dest)
    log.debug(f"Relocated CDF to nested layout: {dest}")
    return dest


def run_process(
    config: ProcessRunConfig,
    *,
    process_fn: Callable[[Path], list[Path]] | None = None,
    upload_fn: Callable[..., tuple[str, str]] | None = None,
    telemetry: HistoricalTelemetry | None = None,
) -> ProcessRunSummary:
    """Run the historical CSV -> CDF (-> S3) orchestrator.

    Parameters
    ----------
    config : ProcessRunConfig
        Run inputs, typically built from CLI args.
    process_fn : callable, optional
        Override for
        :func:`swxsoc_reach.calibration.calibration.process_file`.
        Receives the CSV path and must return a ``list[Path]`` of
        produced CDFs (written into ``cwd`` per the existing
        contract). Tests inject a stub here.
    upload_fn : callable, optional
        Override for
        :func:`swxsoc_reach.historical.s3_upload.upload_cdf_to_s3`.
        Must accept ``(cdf_path, destination_bucket=...)`` keyword
        args and return ``(bucket, s3_key)``.
    telemetry : HistoricalTelemetry, optional
        Override for the telemetry writer/reader.

    Returns
    -------
    ProcessRunSummary
        Aggregate counts. The CLI layer uses these to log the final
        summary line and choose an exit code.
    """
    if process_fn is None:
        from swxsoc_reach.calibration.calibration import process_file

        process_fn = process_file
    if upload_fn is None and config.upload_to_s3:
        from swxsoc_reach.historical.s3_upload import upload_cdf_to_s3

        upload_fn = upload_cdf_to_s3
    if telemetry is None:
        telemetry = HistoricalTelemetry(config.telemetry_path)

    if config.upload_to_s3 and not config.s3_bucket:
        raise ValueError("upload_to_s3=True requires s3_bucket to be set")

    run_id = str(uuid.uuid4())
    config.output_dir.mkdir(parents=True, exist_ok=True)

    state = telemetry.load_state()
    all_dates = list(_iter_dates(config.start_date, config.end_date))

    # Plan: per-day action.
    actionable: list[tuple[date, str, Path | None]] = []
    for d in all_dates:
        csv_path = _match_csv_for_date(
            config.input_dir, d, config.sensor_id, config.output_format
        )
        action = _decide_process_action(
            state.get(d),
            upload_to_s3=config.upload_to_s3,
            csv_available=csv_path is not None,
            retry_failed=config.retry_failed,
        )
        actionable.append((d, action, csv_path))

    # --limit-days counts only days that need work (not skip_existing).
    if config.limit_days is not None:
        kept: list[tuple[date, str, Path | None]] = []
        worked = 0
        for entry in actionable:
            _, action, _ = entry
            if action == "skip_existing":
                kept.append(entry)
                continue
            if worked >= config.limit_days:
                break
            kept.append(entry)
            worked += 1
        actionable = kept

    summary = ProcessRunSummary(
        run_id=run_id,
        days_planned=len(actionable),
        days_attempted=0,
        days_processed=0,
        days_uploaded=0,
        days_skipped_existing=0,
        days_skipped_no_input=0,
        days_failed=0,
    )

    for d, action, csv_path in actionable:
        prior = state.get(d)
        date_iso = d.isoformat()

        if config.dry_run:
            log.info(f"[dry-run] {date_iso} action={action}")
            continue

        if action == "skip_existing":
            log.info(f"{date_iso}: skip (already complete)")
            summary.days_skipped_existing += 1
            continue
        if action == "skip_terminal":
            log.info(f"{date_iso}: skip (prior SKIPPED_NO_INPUT, still no input)")
            summary.days_skipped_no_input += 1
            continue
        if action == "skip_failed":
            log.info(f"{date_iso}: skip (prior FAILED; pass --retry-failed to retry)")
            summary.days_failed += 1
            continue
        if action == "skip_no_input":
            log.info(f"{date_iso}: SKIPPED_NO_INPUT (no matching CSV in input-dir)")
            telemetry.append_row(
                TelemetryRow(
                    run_id=run_id,
                    chunk_date_utc=date_iso,
                    status=STATUS_SKIPPED_NO_INPUT,
                    sensor_id=config.sensor_id,
                    descriptor=config.descriptor,
                    output_format=config.output_format,
                    started_at_utc=utcnow_iso(),
                    finished_at_utc=utcnow_iso(),
                    **_carry_forward(prior),
                )
            )
            summary.days_skipped_no_input += 1
            continue

        # action is run_process or run_upload_only
        carried = _carry_forward(prior)
        base_row = dict(
            run_id=run_id,
            chunk_date_utc=date_iso,
            sensor_id=config.sensor_id,
            descriptor=config.descriptor,
            output_format=config.output_format,
            **carried,
        )

        cdf_path: Path | None = None
        process_seconds = ""
        cdf_size_mb = ""

        if action == "run_process":
            assert csv_path is not None  # invariant from _decide_process_action
            base_row["csv_path"] = str(csv_path)
            summary.days_attempted += 1

            started = utcnow_iso()
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_PROCESS_PENDING,
                    started_at_utc=started,
                    **base_row,
                )
            )

            t0 = time.monotonic()
            try:
                produced = _process_one_day(csv_path, config.output_dir, process_fn)
            except Exception as exc:  # noqa: BLE001 - never abort mid-range
                elapsed = time.monotonic() - t0
                log.error(
                    f"{date_iso}: FAILED at process stage "
                    f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                )
                telemetry.append_row(
                    TelemetryRow(
                        status=STATUS_FAILED,
                        started_at_utc=started,
                        finished_at_utc=utcnow_iso(),
                        process_seconds=f"{elapsed:.3f}",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        **base_row,
                    )
                )
                summary.days_failed += 1
                continue

            elapsed = time.monotonic() - t0
            if not produced:
                log.error(f"{date_iso}: FAILED process_file returned no paths")
                telemetry.append_row(
                    TelemetryRow(
                        status=STATUS_FAILED,
                        started_at_utc=started,
                        finished_at_utc=utcnow_iso(),
                        process_seconds=f"{elapsed:.3f}",
                        error_type="RuntimeError",
                        error_message="process_file returned no output paths",
                        **base_row,
                    )
                )
                summary.days_failed += 1
                continue
            if len(produced) > 1:
                log.warning(
                    f"{date_iso}: process_file returned {len(produced)} paths; "
                    f"recording the first ({produced[0].name})"
                )
            cdf_path = _relocate_to_nested_layout(Path(produced[0]), config.output_dir)
            cdf_size_mb = (
                f"{cdf_path.stat().st_size / (1024 * 1024):.4f}"
                if cdf_path.exists()
                else "0.0000"
            )
            process_seconds = f"{elapsed:.3f}"

            base_row["cdf_path"] = str(cdf_path)
            base_row["cdf_size_mb"] = cdf_size_mb
            base_row["process_seconds"] = process_seconds

            log.info(
                f"{date_iso}: PROCESSED size={cdf_size_mb}MB in {process_seconds}s "
                f"-> {cdf_path}"
            )
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_PROCESSED,
                    started_at_utc=started,
                    finished_at_utc=utcnow_iso(),
                    **base_row,
                )
            )
            summary.days_processed += 1

            if not config.upload_to_s3:
                continue
            # fall through to upload using cdf_path

        elif action == "run_upload_only":
            assert prior is not None
            cdf_path = Path(prior.cdf_path) if prior.cdf_path else None
            if cdf_path is None or not cdf_path.exists():
                # Should not reach here given _decide_process_action,
                # but be defensive.
                log.warning(
                    f"{date_iso}: expected existing CDF for upload-only "
                    f"but path is missing; falling back to skip_failed"
                )
                summary.days_failed += 1
                continue
            base_row["cdf_path"] = str(cdf_path)
            base_row["cdf_size_mb"] = prior.cdf_size_mb
            base_row["process_seconds"] = prior.process_seconds

        # === Upload stage ===
        if not config.upload_to_s3 or upload_fn is None:
            continue

        upload_started = utcnow_iso()
        telemetry.append_row(
            TelemetryRow(
                status=STATUS_UPLOAD_PENDING,
                started_at_utc=upload_started,
                **base_row,
            )
        )

        u0 = time.monotonic()
        try:
            bucket, s3_key = upload_fn(cdf_path, destination_bucket=config.s3_bucket)
        except Exception as exc:  # noqa: BLE001
            u_elapsed = time.monotonic() - u0
            log.error(
                f"{date_iso}: FAILED at upload stage "
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            )
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_FAILED,
                    started_at_utc=upload_started,
                    finished_at_utc=utcnow_iso(),
                    upload_seconds=f"{u_elapsed:.3f}",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    **base_row,
                )
            )
            summary.days_failed += 1
            continue

        u_elapsed = time.monotonic() - u0
        log.info(f"{date_iso}: UPLOADED s3://{bucket}/{s3_key} in {u_elapsed:.1f}s")
        telemetry.append_row(
            TelemetryRow(
                status=STATUS_UPLOADED,
                started_at_utc=upload_started,
                finished_at_utc=utcnow_iso(),
                upload_seconds=f"{u_elapsed:.3f}",
                s3_bucket=bucket,
                s3_key=s3_key,
                **base_row,
            )
        )
        summary.days_uploaded += 1

    return summary
