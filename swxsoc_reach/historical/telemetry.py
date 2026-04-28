"""Append-only CSV telemetry for the historical UDL download orchestrator.

One row is written per attempt at a per-day download. Older rows for the
same ``chunk_date_utc`` are *not* removed; :meth:`DownloadTelemetry.load_state`
returns the most-recent row per date (by ``started_at_utc``), which is
how restart/resume decisions are made.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, fields
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

# Schema column order is the file's source-of-truth for the CSV header.
SCHEMA: tuple[str, ...] = (
    "run_id",
    "chunk_date_utc",
    "window_start_utc",
    "window_end_utc",
    "status",
    "records_downloaded",
    "expected_records",
    "availability_pct",
    "download_seconds",
    "csv_size_mb",
    "csv_path",
    "sensor_id",
    "descriptor",
    "output_format",
    "error_type",
    "error_message",
    "started_at_utc",
    "finished_at_utc",
)

# Status values for the download phase.
STATUS_PENDING = "PENDING"
STATUS_DOWNLOADED = "DOWNLOADED"
STATUS_SKIPPED_NO_DATA = "SKIPPED_NO_DATA"
STATUS_FAILED = "FAILED"

VALID_STATUSES: frozenset[str] = frozenset(
    {STATUS_PENDING, STATUS_DOWNLOADED, STATUS_SKIPPED_NO_DATA, STATUS_FAILED}
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
    records_downloaded: str = ""
    expected_records: str = ""
    availability_pct: str = ""
    download_seconds: str = ""
    csv_size_mb: str = ""
    csv_path: str = ""
    sensor_id: str = ""
    descriptor: str = ""
    output_format: str = ""
    error_type: str = ""
    error_message: str = ""
    started_at_utc: str = ""
    finished_at_utc: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return the row as a ``{column: str}`` dict in schema order."""
        return {f.name: str(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls, raw: dict[str, str]) -> "TelemetryRow":
        """Build a row from a CSV-parsed dict, ignoring unknown columns."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})


class DownloadTelemetry:
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

        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.path.exists() or self.path.stat().st_size == 0

        # newline="" is required by the csv module on all platforms.
        with open(self.path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=SCHEMA)
            if write_header:
                writer.writeheader()
            writer.writerow({col: data.get(col, "") for col in SCHEMA})
            fh.flush()
            os.fsync(fh.fileno())

    def load_state(self) -> dict[date, TelemetryRow]:
        """Return the most-recent row per ``chunk_date_utc``.

        A missing telemetry file returns ``{}``. Rows whose
        ``chunk_date_utc`` is unparseable are skipped with no error
        (treated as if they did not exist) so a hand-edited file cannot
        crash the orchestrator on startup.
        """
        if not self.path.exists():
            return {}

        latest: dict[date, TelemetryRow] = {}
        latest_started: dict[date, str] = {}

        with open(self.path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                row = TelemetryRow.from_dict(raw)
                try:
                    chunk_date = date.fromisoformat(row.chunk_date_utc)
                except ValueError:
                    continue

                started = row.started_at_utc
                # "Most recent" by ISO-8601 ``started_at_utc`` lexicographic
                # compare (we always write UTC). On ties — e.g. PENDING
                # and DOWNLOADED rows from the same attempt share a
                # ``started_at_utc`` — file order breaks the tie via
                # ``>=`` so the later-written row wins.
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
            for raw in reader:
                yield TelemetryRow.from_dict(raw)


def utcnow_iso() -> str:
    """Return an ISO-8601 UTC timestamp suitable for telemetry columns.

    Format: ``YYYY-MM-DDTHH:MM:SS.ffffff+00:00``. Stable lexicographic
    ordering, parseable by :func:`datetime.datetime.fromisoformat`.
    """
    from datetime import timezone

    return datetime.now(tz=timezone.utc).isoformat()
