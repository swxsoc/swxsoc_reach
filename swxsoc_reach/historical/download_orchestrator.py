"""Per-day orchestrator for historical UDL downloads.

Drives :func:`swxsoc_reach.net.udl.download_UDL_reach_window` over an
inclusive UTC date range, recording one or more rows per day in a
:class:`~swxsoc_reach.historical.telemetry.DownloadTelemetry` CSV. Days
that already completed (per telemetry + on-disk artifact) are skipped,
so reruns are idempotent and resumable.

The orchestrator is intentionally sequential at the day level —
concurrency lives inside ``download_UDL_reach_window`` via the existing
thread pool + AIMD rate controller.
"""

from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from astropy.time import Time

from swxsoc_reach import log
from swxsoc_reach.historical.telemetry import (
    DownloadTelemetry,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED_NO_DATA,
    TelemetryRow,
    utcnow_iso,
)
from swxsoc_reach.net import udl as udl_module

# Per-satellite per-dosimeter samples per UTC day at 5-second cadence.
# Used as the upper-bound reference for ``availability_pct``.
_SAMPLES_PER_DOSIMETER_PER_DAY = 17_280  # 24 Hours at 5-second cadence
_REACH_NUM_SATELLITES = 32
_DOSIMETERS_PER_SATELLITE = 2

EXPECTED_RECORDS_ALL = (
    _REACH_NUM_SATELLITES * _DOSIMETERS_PER_SATELLITE * _SAMPLES_PER_DOSIMETER_PER_DAY
)  # 1,105,920
EXPECTED_RECORDS_SINGLE = (
    _DOSIMETERS_PER_SATELLITE * _SAMPLES_PER_DOSIMETER_PER_DAY
)  # 34,560


@dataclass
class DownloadRunConfig:
    """Inputs to :func:`run_download`.

    Mirrors the historical-download CLI flags one-for-one. The CLI
    layer in :mod:`swxsoc_reach.__main__` parses argv into one of these
    instances, then hands it to :func:`run_download`. Tests construct
    it directly to drive the orchestrator without touching argparse.

    Fields
    ------
    - ``start_date`` (``datetime.date``): inclusive UTC start of the
      date range to process.
    - ``end_date`` (``datetime.date``): inclusive UTC end of the date
      range. Must be ``>= start_date``.
    - ``output_dir`` (``pathlib.Path``): directory where per-day
      CSV/JSON artifacts are written. Created if missing.
    - ``telemetry_path`` (``pathlib.Path``): path to the append-only
      telemetry CSV. Created if missing. Conventionally lives inside
      ``output_dir``.
    - ``sensor_id`` (``str``, default ``"ALL"``): REACH sensor
      identifier or ``"ALL"``. Drives chunk size in
      :func:`~swxsoc_reach.net.udl.get_reach_datetimelist` (10-min
      chunks for ``ALL``, 6-hour chunks for a specific sensor) and the
      expected-records baseline used for ``availability_pct``.
    - ``descriptor`` (``str``, default ``"QUICKLOOK"``): UDL
      ``descriptor`` query value.
    - ``output_format`` (``{'csv', 'json'}``, default ``'csv'``):
      output serialization format passed through to the downloader.
    - ``retry_failed`` (``bool``, default ``False``): when ``True``,
      days whose latest telemetry row is ``FAILED`` are re-attempted;
      otherwise they are skipped.
    - ``limit_days`` (``int`` or ``None``): if set, cap the number of
      days *attempted*, counted from the first day not already
      ``DOWNLOADED`` with its artifact on disk.
    - ``dry_run`` (``bool``, default ``False``): when ``True``, no
      network calls and no telemetry writes — only logs the planned
      action per day.
    - ``auth_token`` (``str``): UDL HTTP Basic auth header value.
      Resolved by the CLI layer from
      :func:`swxsoc_reach.net.auth.resolve_udl_auth` (Secrets Manager
      or ``BASICAUTH`` env var).
    - ``max_concurrent_requests`` (``int``, default ``4``): max
      concurrent UDL chunk requests per day; forwarded to
      :func:`~swxsoc_reach.net.udl.download_UDL_reach_window`.
    - ``initial_rate``, ``additive_increase``,
      ``multiplicative_decrease``, ``min_rate``, ``max_rate``
      (``float``): AIMD rate-controller tuning parameters; forwarded
      to :func:`~swxsoc_reach.net.udl.download_UDL_reach_window`.
    """

    start_date: date
    end_date: date
    output_dir: Path
    telemetry_path: Path
    sensor_id: str = "ALL"
    descriptor: str = "QUICKLOOK"
    output_format: str = "csv"
    retry_failed: bool = False
    limit_days: int | None = None
    dry_run: bool = False
    auth_token: str = ""
    max_concurrent_requests: int = 4
    initial_rate: float = 5.0
    additive_increase: float = 1.0
    multiplicative_decrease: float = 0.5
    min_rate: float = 5.0
    max_rate: float = 25.0


@dataclass
class DownloadRunSummary:
    """Aggregate result of one :func:`run_download` invocation.

    Returned to the CLI layer (or any direct caller) so it can log a
    final "X downloaded, Y skipped, Z failed" line and choose a
    process exit code. Per-day detail lives in the telemetry CSV;
    this struct is intentionally just rollups.

    Fields
    ------
    - ``run_id`` (``str``): UUID4 stamped on every telemetry row
      written by this run. Lets operators correlate rows in the
      telemetry CSV with a specific invocation.
    - ``days_planned`` (``int``): days in the inclusive date range
      considered after applying ``--limit-days``. Equals
      ``days_attempted + days_skipped_existing + days_skipped_no_data
      + days_failed`` on a non-dry-run.
    - ``days_attempted`` (``int``): days for which the downloader was
      invoked (regardless of outcome).
    - ``days_downloaded`` (``int``): days that ended in
      ``DOWNLOADED`` (artifact written, telemetry row appended).
    - ``days_skipped_existing`` (``int``): days short-circuited
      because a prior ``DOWNLOADED`` row exists and its CSV artifact
      is still on disk.
    - ``days_skipped_no_data`` (``int``): days that ended in
      ``SKIPPED_NO_DATA`` — either freshly (UDL returned zero
      records, terminal) or via a prior ``SKIPPED_NO_DATA`` row.
    - ``days_failed`` (``int``): days that ended in ``FAILED`` (or
      were skipped because of a prior ``FAILED`` row without
      ``--retry-failed``).
    """

    run_id: str
    days_planned: int
    days_attempted: int
    days_downloaded: int
    days_skipped_existing: int
    days_skipped_no_data: int
    days_failed: int


def _expected_records(sensor_id: str) -> int:
    """Upper-bound reference count for ``availability_pct``."""
    if sensor_id.upper() == "ALL":
        return EXPECTED_RECORDS_ALL
    return EXPECTED_RECORDS_SINGLE


def _iter_dates(start: date, end: date) -> Iterable[date]:
    """Yield each UTC date in ``[start, end]`` inclusive."""
    if end < start:
        raise ValueError(
            f"end_date {end.isoformat()} must be >= start_date {start.isoformat()}"
        )
    current = start
    while current <= end:
        yield current
        current = current + timedelta(days=1)


def _day_window(d: date) -> tuple[Time, Time, str, str]:
    """Return (start_time, end_time, start_iso, end_iso) for a UTC day.

    ``end_time`` is exclusive: ``start + 86400 s``. Matches the existing
    chunk-list semantics so records timestamped in the last second of
    the day are included.
    """
    start_dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    start_t = Time(
        start_dt.replace(tzinfo=None).isoformat(), format="isot", scale="utc"
    )
    end_t = Time(end_dt.replace(tzinfo=None).isoformat(), format="isot", scale="utc")
    return start_t, end_t, start_dt.isoformat(), end_dt.isoformat()


def _decide_action(
    chunk_date: date,
    prior: TelemetryRow | None,
    retry_failed: bool,
) -> str:
    """Return one of ``run`` | ``skip_existing`` | ``skip_terminal`` | ``skip_failed``.

    Decision table (see plan):

    - no prior row → ``run``
    - prior ``DOWNLOADED`` and CSV exists → ``skip_existing``
    - prior ``DOWNLOADED`` and CSV missing → ``run`` (re-download)
    - prior ``SKIPPED_NO_DATA`` → ``skip_terminal``
    - prior ``FAILED`` → ``skip_failed`` unless ``retry_failed`` then ``run``
    - prior ``PENDING`` (interrupted) → ``run``
    """
    if prior is None:
        return "run"
    if prior.status == STATUS_DOWNLOADED:
        csv_path = prior.csv_path
        if csv_path and Path(csv_path).exists():
            return "skip_existing"
        return "run"
    if prior.status == STATUS_SKIPPED_NO_DATA:
        return "skip_terminal"
    if prior.status == STATUS_FAILED:
        return "run" if retry_failed else "skip_failed"
    # PENDING or unknown → re-run.
    return "run"


def run_download(
    config: DownloadRunConfig,
    *,
    download_fn: Callable[..., Path] | None = None,
    telemetry: DownloadTelemetry | None = None,
) -> DownloadRunSummary:
    """Run the historical UDL download orchestrator.

    Steps performed, in order:

    1. **Initialize.** Generate a fresh ``run_id`` (UUID4) used to
       stamp every telemetry row written by this invocation. Ensure
       ``config.output_dir`` exists.
    2. **Load prior state.** Read the telemetry CSV at
       ``config.telemetry_path`` and reduce it to a ``{date: latest
       row}`` mapping via
       :meth:`~swxsoc_reach.historical.telemetry.DownloadTelemetry.load_state`.
       Missing/empty file is treated as no prior state.
    3. **Plan.** Expand ``[start_date, end_date]`` into one
       UTC-midnight-bounded window per day, decide an action per day
       via :func:`_decide_action` (``run`` / ``skip_existing`` /
       ``skip_terminal`` / ``skip_failed``), and apply
       ``--limit-days`` by counting only days whose action is not
       ``skip_existing``.
    4. **Execute, sequentially per day.** For each planned day:

       a. If ``config.dry_run``, log the action and continue (no
          telemetry rows written, no network calls).
       b. For skip actions, log the reason, increment the matching
          summary counter, and continue.
       c. For ``run`` actions, append a ``PENDING`` row, then invoke
          ``download_fn`` with absolute UTC ``start_time`` /
          ``end_time`` (00:00:00 → next day 00:00:00, exclusive end)
          and the AIMD knobs from ``config``.

    5. **Classify outcomes per attempted day.**

       - On success: append a ``DOWNLOADED`` row with
         ``records_downloaded``, ``availability_pct`` (vs the
         per-sensor expected-records baseline), ``download_seconds``,
         ``csv_size_mb``, and ``csv_path``.
       - On :class:`ValueError` from the downloader (its "no records"
         signal): append a terminal ``SKIPPED_NO_DATA`` row.
       - On any other exception: append a ``FAILED`` row with
         ``error_type`` and ``error_message``. **The orchestrator
         never aborts mid-range — it continues to the next day.**

    6. **Return** an aggregated :class:`DownloadRunSummary`.

    Concurrency: this function is sequential at the day level.
    Per-day concurrency lives inside ``download_fn`` (the existing
    thread pool + AIMD rate controller in
    :func:`~swxsoc_reach.net.udl.download_UDL_reach_window`).

    Parameters
    ----------
    config : DownloadRunConfig
        Run inputs, typically built from CLI args.
    download_fn : callable, optional
        Override for
        :func:`swxsoc_reach.net.udl.download_UDL_reach_window`. Must
        accept the same keyword arguments and return the path to the
        written artifact, or raise ``ValueError`` for an empty window.
        Tests inject a stub here; production callers leave it ``None``.
    telemetry : DownloadTelemetry, optional
        Override for the telemetry writer/reader. Defaults to one
        backed by ``config.telemetry_path``. Tests may inject a
        pre-populated instance to simulate restart scenarios.

    Returns
    -------
    DownloadRunSummary
        Aggregate counts for the run. The CLI layer uses these to log
        the final summary line and choose an exit code.
    """
    if download_fn is None:
        download_fn = udl_module.download_UDL_reach_window
    if telemetry is None:
        telemetry = DownloadTelemetry(config.telemetry_path)

    run_id = str(uuid.uuid4())
    config.output_dir.mkdir(parents=True, exist_ok=True)

    state = telemetry.load_state()

    all_dates = list(_iter_dates(config.start_date, config.end_date))

    # Determine which days need work in order — used for ``--limit-days``
    # which counts from the first not-yet-complete day.
    actionable: list[tuple[date, str]] = []
    for d in all_dates:
        action = _decide_action(d, state.get(d), config.retry_failed)
        actionable.append((d, action))

    # Apply --limit-days to the first N days that are not ``skip_existing``.
    if config.limit_days is not None:
        kept: list[tuple[date, str]] = []
        worked = 0
        for d, action in actionable:
            if action == "skip_existing":
                kept.append((d, action))
                continue
            if worked >= config.limit_days:
                break
            kept.append((d, action))
            worked += 1
        actionable = kept

    summary = DownloadRunSummary(
        run_id=run_id,
        days_planned=len(actionable),
        days_attempted=0,
        days_downloaded=0,
        days_skipped_existing=0,
        days_skipped_no_data=0,
        days_failed=0,
    )

    for d, action in actionable:
        start_t, end_t, start_iso, end_iso = _day_window(d)
        prior = state.get(d)

        if config.dry_run:
            log.info(
                f"[dry-run] {d.isoformat()} action={action}"
                + (f" prior_status={prior.status}" if prior else "")
            )
            continue

        if action == "skip_existing":
            log.info(f"{d.isoformat()}: skip (already DOWNLOADED at {prior.csv_path})")
            summary.days_skipped_existing += 1
            continue
        if action == "skip_terminal":
            log.info(f"{d.isoformat()}: skip (prior SKIPPED_NO_DATA)")
            summary.days_skipped_no_data += 1
            continue
        if action == "skip_failed":
            log.info(
                f"{d.isoformat()}: skip (prior FAILED; pass --retry-failed to retry)"
            )
            summary.days_failed += 1
            continue

        # action == "run"
        summary.days_attempted += 1
        started = utcnow_iso()
        base_row = dict(
            run_id=run_id,
            chunk_date_utc=d.isoformat(),
            window_start_utc=start_iso,
            window_end_utc=end_iso,
            sensor_id=config.sensor_id,
            descriptor=config.descriptor,
            output_format=config.output_format,
            expected_records=str(_expected_records(config.sensor_id)),
            started_at_utc=started,
        )
        telemetry.append_row(TelemetryRow(status=STATUS_PENDING, **base_row))

        t0 = time.monotonic()
        try:
            csv_path = download_fn(
                auth_token=config.auth_token,
                sensor_id=config.sensor_id,
                descriptor=config.descriptor,
                output_format=config.output_format,
                start_time=start_t,
                end_time=end_t,
                output_dir=config.output_dir,
                max_concurrent_requests=config.max_concurrent_requests,
                initial_rate=config.initial_rate,
                additive_increase=config.additive_increase,
                multiplicative_decrease=config.multiplicative_decrease,
                min_rate=config.min_rate,
                max_rate=config.max_rate,
            )
        except ValueError as exc:
            # ``download_UDL_reach_window`` raises ValueError for empty
            # windows. Treat as terminal SKIPPED_NO_DATA.
            elapsed = time.monotonic() - t0
            log.info(f"{d.isoformat()}: SKIPPED_NO_DATA ({exc})")
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_SKIPPED_NO_DATA,
                    download_seconds=f"{elapsed:.3f}",
                    error_message=str(exc),
                    finished_at_utc=utcnow_iso(),
                    **base_row,
                )
            )
            summary.days_skipped_no_data += 1
            continue
        except Exception as exc:  # noqa: BLE001 — orchestrator must not abort
            elapsed = time.monotonic() - t0
            log.error(
                f"{d.isoformat()}: FAILED {type(exc).__name__}: {exc}\n"
                f"{traceback.format_exc()}"
            )
            telemetry.append_row(
                TelemetryRow(
                    status=STATUS_FAILED,
                    download_seconds=f"{elapsed:.3f}",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    finished_at_utc=utcnow_iso(),
                    **base_row,
                )
            )
            summary.days_failed += 1
            continue

        elapsed = time.monotonic() - t0
        records = _count_records(csv_path, config.output_format)
        size_mb = csv_path.stat().st_size / (1024 * 1024) if csv_path.exists() else 0.0
        expected = _expected_records(config.sensor_id)
        availability = (records / expected * 100.0) if expected else 0.0

        log.info(
            f"{d.isoformat()}: DOWNLOADED records={records} "
            f"availability={availability:.1f}% "
            f"size={size_mb:.2f}MB in {elapsed:.1f}s -> {csv_path}"
        )
        telemetry.append_row(
            TelemetryRow(
                status=STATUS_DOWNLOADED,
                records_downloaded=str(records),
                availability_pct=f"{availability:.4f}",
                download_seconds=f"{elapsed:.3f}",
                csv_size_mb=f"{size_mb:.4f}",
                csv_path=str(csv_path),
                finished_at_utc=utcnow_iso(),
                **base_row,
            )
        )
        summary.days_downloaded += 1

    return summary


def _count_records(csv_path: Path, output_format: str) -> int:
    """Count data records in the just-written file.

    Cheap line-count for CSV (header subtracted); for JSON, parse and
    return ``len(...)``. Errors fall through as 0 — telemetry is not
    worth crashing the run over.
    """
    try:
        if output_format == "csv":
            with open(csv_path, "r", encoding="utf-8") as fh:
                # subtract one for the header row
                return max(sum(1 for _ in fh) - 1, 0)
        if output_format == "json":
            import json

            with open(csv_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            return len(payload) if isinstance(payload, list) else 0
    except OSError:
        return 0
    return 0
