"""Append-only CSV telemetry for the historical UDL download orchestrator.

One row is written per attempt at a per-day download. Older rows for the
same ``chunk_date_utc`` are *not* removed; :meth:`HistoricalTelemetry.load_state`
returns the most-recent row per date (by ``started_at_utc``), which is
how restart/resume decisions are made.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, fields, replace
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from swxsoc_reach import config as swxsoc_config

# Schema column order is the file's source-of-truth for the CSV header.
SCHEMA: tuple[str, ...] = (
    "run_id",
    "chunk_date_utc",
    "window_start_utc",
    "window_end_utc",
    "status",
    # Download Columns
    "records_downloaded",
    "expected_records",
    "availability_pct",
    "download_seconds",
    "csv_size_mb",
    "csv_path",
    "sensor_id",
    "descriptor",
    "data_level",
    "output_format",
    "error_type",
    "error_message",
    "started_at_utc",
    "finished_at_utc",
    # Processing Columns
    "process_seconds",
    "cdf_size_mb",
    "cdf_path",
    # Upload Columns
    "upload_seconds",
    "s3_bucket",
    "s3_key",
)

# Status values for the download phase.
STATUS_DOWNLOAD_PENDING = "DOWNLOAD_PENDING"
STATUS_DOWNLOADED = "DOWNLOADED"
STATUS_SKIPPED_NO_DATA = "SKIPPED_NO_DATA"
STATUS_FAILED = "FAILED"

# Status values for the process / upload phase.
STATUS_PROCESS_PENDING = "PROCESS_PENDING"
STATUS_PROCESSED = "PROCESSED"
STATUS_UPLOAD_PENDING = "UPLOAD_PENDING"
STATUS_UPLOADED = "UPLOADED"
STATUS_SKIPPED_NO_INPUT = "SKIPPED_NO_INPUT"

VALID_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_DOWNLOAD_PENDING,
        STATUS_DOWNLOADED,
        STATUS_SKIPPED_NO_DATA,
        STATUS_FAILED,
        STATUS_PROCESS_PENDING,
        STATUS_PROCESSED,
        STATUS_UPLOAD_PENDING,
        STATUS_UPLOADED,
        STATUS_SKIPPED_NO_INPUT,
    }
)

DOWNLOAD_PHASE_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_DOWNLOAD_PENDING,
        STATUS_DOWNLOADED,
        STATUS_SKIPPED_NO_DATA,
    }
)


@dataclass
class TelemetryRow:
    """One row in the download telemetry CSV.

    All fields default to ``""`` so callers can populate just the
    columns relevant for a given status (e.g. a ``PENDING`` row has no
    ``finished_at_utc`` yet, a ``SKIPPED_NO_DATA`` row has no
    ``csv_path``, etc.).
    """

    run_id: str = ""
    chunk_date_utc: str = ""
    window_start_utc: str = ""
    window_end_utc: str = ""
    status: str = ""
    # Download Columns
    records_downloaded: str = ""
    expected_records: str = ""
    availability_pct: str = ""
    download_seconds: str = ""
    csv_size_mb: str = ""
    csv_path: str = ""
    sensor_id: str = ""
    descriptor: str = ""
    data_level: str = ""
    output_format: str = ""
    error_type: str = ""
    error_message: str = ""
    started_at_utc: str = ""
    finished_at_utc: str = ""
    # Processing Columns
    process_seconds: str = ""
    cdf_size_mb: str = ""
    cdf_path: str = ""
    # Upload Columns
    upload_seconds: str = ""
    s3_bucket: str = ""
    s3_key: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return the row as a ``{column: str}`` dict in schema order."""
        return {f.name: str(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls, raw: dict[str, str]) -> "TelemetryRow":
        """Build a row from a CSV-parsed dict, ignoring unknown columns."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})


class HistoricalTelemetry:
    """Append-only CSV writer / reader for download telemetry."""

    def __init__(self, telemetry_path: Path | str):
        self.path = Path(telemetry_path)

    def append_row(self, row: TelemetryRow | dict) -> None:
        """Append a single row, writing the header on first create.

        The file is flushed and ``fsync``-ed before returning so an
        interrupted run leaves the telemetry on disk in a consistent
        state.
        """
        if isinstance(row, TelemetryRow):
            data = row.to_dict()
        else:
            unknown = set(row) - set(SCHEMA)
            if unknown:
                raise ValueError(
                    f"Unknown telemetry columns: {sorted(unknown)}. Allowed: {SCHEMA}."
                )
            data = {col: str(row.get(col, "")) for col in SCHEMA}

        # Reject invalid statuses early — they're the sole field the
        # orchestrator branches on.
        status = data.get("status", "")
        if status and status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid telemetry status {status!r}. "
                f"Allowed: {sorted(VALID_STATUSES)}."
            )

        level = data.get("data_level", "")
        if level and level not in valid_levels():
            raise ValueError(
                f"Invalid telemetry data_level {level!r}. "
                f"Allowed: {list(valid_levels())}."
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._upgrade_schema_if_needed()
        write_header = not self.path.exists() or self.path.stat().st_size == 0

        # newline="" is required by the csv module on all platforms.
        with open(self.path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=SCHEMA)
            if write_header:
                writer.writeheader()
            writer.writerow({col: data.get(col, "") for col in SCHEMA})
            fh.flush()
            os.fsync(fh.fileno())

    def _upgrade_schema_if_needed(self) -> None:
        """Rewrite legacy-header files to current SCHEMA in-place."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return

        with open(self.path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = tuple(reader.fieldnames or ())
            if header == SCHEMA:
                return
            migrated = [_row_from_reader(raw, header).to_dict() for raw in reader]

        with open(self.path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=SCHEMA)
            writer.writeheader()
            writer.writerows(migrated)
            fh.flush()
            os.fsync(fh.fileno())

    def load_state(self) -> dict[tuple[date, str], list[TelemetryRow]]:
        """Return the most-recent row per ``(date, level, basename)``.

        A missing telemetry file returns ``{}``. Rows whose
        ``chunk_date_utc`` is unparseable are skipped with no error
        (treated as if they did not exist) so a hand-edited file cannot
        crash the orchestrator on startup.
        """
        if not self.path.exists():
            return {}

        latest: dict[tuple[date, str, str], TelemetryRow] = {}
        latest_started: dict[tuple[date, str, str], str] = {}

        with open(self.path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = tuple(reader.fieldnames or ())
            for raw in reader:
                row = _row_from_reader(raw, header)
                try:
                    chunk_date = date.fromisoformat(row.chunk_date_utc)
                except ValueError:
                    continue

                for normalized in _normalize_row_levels(row):
                    key = (
                        chunk_date,
                        normalized.data_level,
                        _output_basename(normalized),
                    )
                    started = normalized.started_at_utc
                    if key not in latest or started >= latest_started.get(key, ""):
                        latest[key] = normalized
                        latest_started[key] = started

        grouped: dict[tuple[date, str], list[TelemetryRow]] = {}
        for (chunk_date, level, _basename), row in latest.items():
            grouped.setdefault((chunk_date, level), []).append(row)

        # Hide non-orphan pending rows in the state view. If a run has
        # already emitted a finalized row for the same run/file identity,
        # its PENDING precursor is not actionable for resume decisions.
        for key, rows in list(grouped.items()):
            grouped[key] = _prune_pending_rows(rows)
        return grouped

    def load_download_state(self) -> dict[date, TelemetryRow]:
        """Return downloader-only latest state keyed by date.

        This view exists to preserve download restart logic while process
        telemetry now stores multiple levels and per-file rows.
        """
        level_state = self.load_state()
        latest: dict[date, TelemetryRow] = {}
        latest_started: dict[date, str] = {}

        for (chunk_date, level), rows in level_state.items():
            if level not in ("", "raw"):
                continue
            for row in rows:
                if not _is_download_row(row):
                    continue
                started = row.started_at_utc
                if chunk_date not in latest or started >= latest_started.get(
                    chunk_date, ""
                ):
                    latest[chunk_date] = row
                    latest_started[chunk_date] = started
        return latest

    def iter_rows(self) -> Iterable[TelemetryRow]:
        """Yield every row in file order. Useful for tests/debug."""
        if not self.path.exists():
            return
        with open(self.path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = tuple(reader.fieldnames or ())
            for raw in reader:
                yield _row_from_reader(raw, header)


def utcnow_iso() -> str:
    """Return an ISO-8601 UTC timestamp suitable for telemetry columns.

    Format: ``YYYY-MM-DDTHH:MM:SS.ffffff+00:00``. Stable lexicographic
    ordering, parseable by :func:`datetime.datetime.fromisoformat`.
    """
    from datetime import timezone

    return datetime.now(tz=timezone.utc).isoformat()


def valid_levels() -> tuple[str, ...]:
    """Return configured mission levels in order."""
    levels = tuple(swxsoc_config["mission"].get("valid_data_levels", []))
    if not levels:
        return ("raw", "l1c", "l2", "l3")
    return levels


def level_order(level: str) -> int:
    """Return ordinal index of a data level from mission config."""
    return valid_levels().index(level)


def prior_level(level: str) -> str | None:
    """Return immediate predecessor level, or None for first."""
    levels = valid_levels()
    idx = levels.index(level)
    if idx == 0:
        return None
    return levels[idx - 1]


def _normalize_row_levels(row: TelemetryRow) -> list[TelemetryRow]:
    """Return one or more level-tagged rows for state loading.

    Legacy rows may not have ``data_level`` set but can still encode
    raw/cdf artifacts. We synthesize those levels at read time without
    mutating the on-disk CSV.
    """
    if row.data_level:
        return [row]

    normalized: list[TelemetryRow] = []
    if row.csv_path:
        normalized.append(replace(row, data_level="raw"))
    if row.cdf_path:
        normalized.append(replace(row, data_level="l1c"))
    if normalized:
        return normalized
    return [row]


def _output_basename(row: TelemetryRow) -> str:
    """Compute row identity suffix for per-file dedup."""
    if row.cdf_path:
        return Path(row.cdf_path).name
    if row.csv_path:
        return Path(row.csv_path).name
    return ""


def _is_download_row(row: TelemetryRow) -> bool:
    """Return True when a row belongs to the download phase."""
    if row.status in DOWNLOAD_PHASE_STATUSES:
        return True
    if row.status != STATUS_FAILED:
        return False
    # Disambiguate FAILED rows shared by process/upload stages.
    return not any((row.process_seconds, row.cdf_path, row.upload_seconds, row.s3_key))


def _row_from_reader(raw: dict[str, str], header: tuple[str, ...]) -> TelemetryRow:
    """Build a TelemetryRow from DictReader output for mixed schema files."""
    expanded = dict(raw)
    overflow = expanded.pop(None, None)
    if overflow:
        missing = [col for col in SCHEMA if col not in header]
        for col, value in zip(missing, overflow):
            expanded[col] = value
    return TelemetryRow.from_dict(expanded)


def _prune_pending_rows(rows: list[TelemetryRow]) -> list[TelemetryRow]:
    """Drop PENDING rows that already have a finalized successor."""
    process_finalized_run_ids = {
        r.run_id for r in rows if r.status != STATUS_PROCESS_PENDING and r.run_id
    }
    upload_finalized = {
        (r.run_id, r.cdf_path)
        for r in rows
        if r.status in (STATUS_UPLOADED, STATUS_FAILED) and r.run_id and r.cdf_path
    }

    pruned: list[TelemetryRow] = []
    for row in rows:
        if row.status == STATUS_PROCESS_PENDING and row.run_id in process_finalized_run_ids:
            continue
        if (
            row.status == STATUS_UPLOAD_PENDING
            and row.run_id
            and row.cdf_path
            and (row.run_id, row.cdf_path) in upload_finalized
        ):
            continue
        pruned.append(row)
    return pruned
