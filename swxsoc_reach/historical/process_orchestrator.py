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
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from swxsoc_reach import log
from swxsoc_reach.historical._dates import iter_dates as _iter_dates
from swxsoc_reach.historical.telemetry import (
    HistoricalTelemetry,
    STATUS_FAILED,
    STATUS_PROCESS_PENDING,
    STATUS_PROCESSED,
    STATUS_SKIPPED_NO_INPUT,
    STATUS_UPLOAD_PENDING,
    STATUS_UPLOADED,
    TelemetryRow,
    prior_level,
    utcnow_iso,
    valid_levels,
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
    target_level: str = "l1c"
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
    files_processed: int
    files_uploaded: int
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
    prior_rows: list[TelemetryRow],
    *,
    upload_to_s3: bool,
    input_available: bool,
    retry_failed: bool,
) -> str:
    if not prior_rows:
        return "run_process" if input_available else "skip_no_input"

    finalized_run_ids = {
        r.run_id for r in prior_rows if r.run_id and r.status != STATUS_PROCESS_PENDING
    }
    orphan_process_pending = any(
        r.status == STATUS_PROCESS_PENDING and r.run_id not in finalized_run_ids
        for r in prior_rows
    )

    upload_finalized = {
        (r.run_id, r.cdf_path)
        for r in prior_rows
        if r.status in (STATUS_UPLOADED, STATUS_FAILED) and r.cdf_path
    }
    orphan_upload_pending = any(
        r.status == STATUS_UPLOAD_PENDING
        and r.cdf_path
        and (r.run_id, r.cdf_path) not in upload_finalized
        for r in prior_rows
    )

    failed_rows = [r for r in prior_rows if r.status == STATUS_FAILED]
    process_failed = any(not r.cdf_path for r in failed_rows)
    upload_failed = [r for r in failed_rows if r.cdf_path]

    if orphan_process_pending:
        return "run_process" if input_available else "skip_no_input"

    if process_failed:
        if retry_failed:
            return "run_process" if input_available else "skip_no_input"
        return "skip_failed"

    if upload_failed and retry_failed and upload_to_s3:
        if any(Path(r.cdf_path).exists() for r in upload_failed):
            return "run_upload_only"

    if upload_failed and not retry_failed:
        return "skip_failed"

    processed_rows = [r for r in prior_rows if r.status == STATUS_PROCESSED and r.cdf_path]
    has_processed_missing_path = any(
        r.status == STATUS_PROCESSED and not r.cdf_path for r in prior_rows
    )
    uploaded_paths = {
        r.cdf_path for r in prior_rows if r.status == STATUS_UPLOADED and r.cdf_path
    }

    all_terminal = all(r.status in (STATUS_PROCESSED, STATUS_UPLOADED) for r in prior_rows)
    if all_terminal:
        if has_processed_missing_path:
            return "run_process" if input_available else "skip_no_input"
        if not upload_to_s3:
            if not processed_rows:
                return "skip_existing"
            if all(Path(r.cdf_path).exists() for r in processed_rows):
                return "skip_existing"
            return "run_process" if input_available else "skip_no_input"
        if all(r.cdf_path in uploaded_paths for r in processed_rows):
            return "skip_existing"

    if upload_to_s3 and (orphan_upload_pending or processed_rows):
        missing_upload = [
            r for r in processed_rows if r.cdf_path not in uploaded_paths and Path(r.cdf_path).exists()
        ]
        if missing_upload or orphan_upload_pending:
            return "run_upload_only"

    return "run_process" if input_available else "skip_no_input"


def _carry_forward(source_row: TelemetryRow | None) -> dict[str, str]:
    """Carry Phase 1 download columns forward onto a Phase 2 row.

    Keeps the most-recent row per day self-describing in the telemetry
    CSV. When no prior row exists, returns blank values so column
    positions are populated.
    """
    if source_row is None:
        return {
            "records_downloaded": "",
            "expected_records": "",
            "availability_pct": "",
            "download_seconds": "",
            "csv_size_mb": "",
            "csv_path": "",
        }
    return {
        "records_downloaded": source_row.records_downloaded,
        "expected_records": source_row.expected_records,
        "availability_pct": source_row.availability_pct,
        "download_seconds": source_row.download_seconds,
        "csv_size_mb": source_row.csv_size_mb,
        "csv_path": source_row.csv_path,
    }


def _resolve_input_for_level(
    state: dict[tuple[date, str], list[TelemetryRow]],
    day: date,
    target_level: str,
    input_dir: Path,
    sensor_id: str,
    output_format: str,
) -> tuple[Path | None, str]:
    """Resolve input artifact path for a target level/day."""
    if target_level == "l1c":
        csv_path = _match_csv_for_date(input_dir, day, sensor_id, output_format)
        if csv_path is None:
            return None, "no matching CSV in input-dir"
        return csv_path, "ok"

    source_level = prior_level(target_level)
    if source_level is None:
        return None, f"{target_level} has no prior level"

    prior_rows = state.get((day, source_level), [])
    if not prior_rows:
        return None, f"no prior-level rows at {source_level}"

    cdf_rows = [
        r
        for r in prior_rows
        if r.cdf_path and r.cdf_path.lower().endswith(".cdf") and Path(r.cdf_path).exists()
    ]
    if target_level == "l2":
        if len(cdf_rows) == 1:
            return Path(cdf_rows[0].cdf_path), "ok"
        if len(cdf_rows) > 1:
            return None, "ambiguous prior level rows for l2"
        return None, "prior-level CDF missing on disk"

    return None, "ambiguous prior level for l3+ (not implemented)"


def _most_recent_row(rows: list[TelemetryRow]) -> TelemetryRow | None:
    if not rows:
        return None
    return max(rows, key=lambda r: r.started_at_utc)


def _make_row_base(
    *,
    run_id: str,
    date_iso: str,
    config: ProcessRunConfig,
    carried: dict[str, str],
    cdf_path: str = "",
    cdf_size_mb: str = "",
    process_seconds: str = "",
) -> dict[str, str]:
    return dict(
        run_id=run_id,
        chunk_date_utc=date_iso,
        sensor_id=config.sensor_id,
        descriptor=config.descriptor,
        data_level=config.target_level,
        output_format=config.output_format,
        cdf_path=cdf_path,
        cdf_size_mb=cdf_size_mb,
        process_seconds=process_seconds,
        **carried,
    )


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
    if config.target_level not in valid_levels():
        raise ValueError(
            f"target_level={config.target_level!r} must be one of {list(valid_levels())}"
        )

    run_id = str(uuid.uuid4())
    config.output_dir.mkdir(parents=True, exist_ok=True)

    state = telemetry.load_state()
    all_dates = list(_iter_dates(config.start_date, config.end_date))

    # Plan: per-day action.
    actionable: list[tuple[date, str, Path | None, str]] = []
    for d in all_dates:
        input_path, reason = _resolve_input_for_level(
            state,
            d,
            config.target_level,
            config.input_dir,
            config.sensor_id,
            config.output_format,
        )
        prior_rows = state.get((d, config.target_level), [])
        action = _decide_process_action(
            prior_rows,
            upload_to_s3=config.upload_to_s3,
            input_available=input_path is not None,
            retry_failed=config.retry_failed,
        )
        actionable.append((d, action, input_path, reason))

    # --limit-days counts only days that need work (not skip_existing).
    if config.limit_days is not None:
        kept: list[tuple[date, str, Path | None, str]] = []
        worked = 0
        for entry in actionable:
            _, action, _, _ = entry
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
        files_processed=0,
        files_uploaded=0,
        days_skipped_existing=0,
        days_skipped_no_input=0,
        days_failed=0,
    )

    for d, action, input_path, reason in actionable:
        prior_rows = state.get((d, config.target_level), [])
        date_iso = d.isoformat()
        day_failed = False
        day_processed = 0
        day_uploaded = 0

        if config.dry_run:
            log.info(f"[dry-run] {date_iso} level={config.target_level} action={action}")
            continue

        if action == "skip_existing":
            log.info(f"{date_iso}: skip (already complete at level {config.target_level})")
            summary.days_skipped_existing += 1
            continue
        if action == "skip_failed":
            log.info(f"{date_iso}: skip (prior FAILED; pass --retry-failed to retry)")
            summary.days_failed += 1
            continue
        if action == "skip_no_input":
            log.info(f"{date_iso}: SKIPPED_NO_INPUT ({reason})")
            carried = _carry_forward(_most_recent_row(state.get((d, "raw"), [])))
            telemetry.append_row(
                TelemetryRow(
                    run_id=run_id,
                    chunk_date_utc=date_iso,
                    status=STATUS_SKIPPED_NO_INPUT,
                    sensor_id=config.sensor_id,
                    descriptor=config.descriptor,
                    data_level=config.target_level,
                    output_format=config.output_format,
                    started_at_utc=utcnow_iso(),
                    finished_at_utc=utcnow_iso(),
                    **carried,
                )
            )
            summary.days_skipped_no_input += 1
            continue

        source_rows = state.get((d, "raw"), [])
        if config.target_level != "l1c":
            prior_source = prior_level(config.target_level)
            source_rows = state.get((d, prior_source), []) if prior_source else []
        carried = _carry_forward(_most_recent_row(source_rows))
        newly_processed_rows: list[TelemetryRow] = []

        if action == "run_process":
            assert input_path is not None
            summary.days_attempted += 1

            started = utcnow_iso()
            pending_row = _make_row_base(
                run_id=run_id,
                date_iso=date_iso,
                config=config,
                carried=carried,
            )
            if config.target_level == "l1c":
                pending_row["csv_path"] = str(input_path)
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_PROCESS_PENDING,
                    started_at_utc=started,
                    **pending_row,
                )
            )

            t0 = time.monotonic()
            try:
                produced = _process_one_day(input_path, config.output_dir, process_fn)
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
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        **_make_row_base(
                            run_id=run_id,
                            date_iso=date_iso,
                            config=config,
                            carried=carried,
                            process_seconds=f"{elapsed:.3f}",
                        ),
                    )
                )
                day_failed = True
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
                        error_type="RuntimeError",
                        error_message="process_file returned no output paths",
                        **_make_row_base(
                            run_id=run_id,
                            date_iso=date_iso,
                            config=config,
                            carried=carried,
                            process_seconds=f"{elapsed:.3f}",
                        ),
                    )
                )
                day_failed = True
                summary.days_failed += 1
                continue
            process_seconds = f"{elapsed:.3f}"
            for produced_path in produced:
                relocated = _relocate_to_nested_layout(Path(produced_path), config.output_dir)
                cdf_size_mb = (
                    f"{relocated.stat().st_size / (1024 * 1024):.4f}"
                    if relocated.exists()
                    else "0.0000"
                )
                processed_row_data = _make_row_base(
                    run_id=run_id,
                    date_iso=date_iso,
                    config=config,
                    carried=carried,
                    cdf_path=str(relocated),
                    cdf_size_mb=cdf_size_mb,
                    process_seconds=process_seconds,
                )
                telemetry.append_row(
                    TelemetryRow(
                        status=STATUS_PROCESSED,
                        started_at_utc=started,
                        finished_at_utc=utcnow_iso(),
                        **processed_row_data,
                    )
                )
                newly_processed_rows.append(TelemetryRow(status=STATUS_PROCESSED, **processed_row_data))
                day_processed += 1
                summary.files_processed += 1

            if day_processed == 0:
                day_failed = True

            if not config.upload_to_s3:
                if day_processed > 0:
                    summary.days_processed += 1
                if day_failed:
                    summary.days_failed += 1
                continue

        elif action == "run_upload_only":
            summary.days_attempted += 1

        # === Upload stage ===
        if not config.upload_to_s3 or upload_fn is None:
            if day_processed > 0:
                summary.days_processed += 1
            if day_failed:
                summary.days_failed += 1
            continue

        uploaded_paths = {
            r.cdf_path for r in prior_rows if r.status == STATUS_UPLOADED and r.cdf_path
        }
        upload_candidates: dict[str, TelemetryRow] = {}

        for row in newly_processed_rows:
            if row.cdf_path:
                upload_candidates[row.cdf_path] = row

        for row in prior_rows:
            if row.status == STATUS_PROCESSED and row.cdf_path and row.cdf_path not in uploaded_paths:
                if Path(row.cdf_path).exists():
                    upload_candidates.setdefault(row.cdf_path, row)
            if (
                config.retry_failed
                and row.status == STATUS_FAILED
                and row.cdf_path
                and row.cdf_path not in uploaded_paths
                and Path(row.cdf_path).exists()
            ):
                upload_candidates.setdefault(row.cdf_path, row)

        for upload_row in upload_candidates.values():
            upload_started = utcnow_iso()
            row_base = _make_row_base(
                run_id=run_id,
                date_iso=date_iso,
                config=config,
                carried=carried,
                cdf_path=upload_row.cdf_path,
                cdf_size_mb=upload_row.cdf_size_mb,
                process_seconds=upload_row.process_seconds,
            )
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_UPLOAD_PENDING,
                    started_at_utc=upload_started,
                    **row_base,
                )
            )

            u0 = time.monotonic()
            try:
                bucket, s3_key = upload_fn(
                    Path(upload_row.cdf_path), destination_bucket=config.s3_bucket
                )
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
                        **row_base,
                    )
                )
                day_failed = True
                continue

            u_elapsed = time.monotonic() - u0
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_UPLOADED,
                    started_at_utc=upload_started,
                    finished_at_utc=utcnow_iso(),
                    upload_seconds=f"{u_elapsed:.3f}",
                    s3_bucket=bucket,
                    s3_key=s3_key,
                    **row_base,
                )
            )
            day_uploaded += 1
            summary.files_uploaded += 1

        if day_processed > 0:
            summary.days_processed += 1
        if day_uploaded > 0:
            summary.days_uploaded += 1
        if day_failed:
            summary.days_failed += 1

    return summary
