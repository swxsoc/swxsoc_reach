"""Tests for ``swxsoc_reach.historical.telemetry``."""

from __future__ import annotations

import csv
from datetime import date

import pytest

from swxsoc_reach.historical import telemetry as tm
from swxsoc_reach.historical.telemetry import (
    DownloadTelemetry,
    SCHEMA,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED_NO_DATA,
    TelemetryRow,
)


def _row(**overrides) -> TelemetryRow:
    base = dict(
        run_id="run-1",
        chunk_date_utc="2026-01-01",
        window_start_utc="2026-01-01T00:00:00+00:00",
        window_end_utc="2026-01-02T00:00:00+00:00",
        status=STATUS_PENDING,
        sensor_id="REACH-1",
        descriptor="QUICKLOOK",
        output_format="csv",
        started_at_utc="2026-01-01T00:00:00.000000+00:00",
    )
    base.update(overrides)
    return TelemetryRow(**base)


def test_append_row_writes_header_then_appends(tmp_path):
    path = tmp_path / "download_telemetry.csv"
    t = DownloadTelemetry(path)

    t.append_row(_row(status=STATUS_PENDING))
    t.append_row(
        _row(
            status=STATUS_DOWNLOADED,
            records_downloaded="1234",
            csv_path="/out/foo.csv",
            finished_at_utc="2026-01-01T00:01:00.000000+00:00",
        )
    )

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = list(reader)

    # Header + 2 data rows
    assert rows[0] == list(SCHEMA)
    assert len(rows) == 3
    assert rows[1][SCHEMA.index("status")] == STATUS_PENDING
    assert rows[2][SCHEMA.index("status")] == STATUS_DOWNLOADED
    assert rows[2][SCHEMA.index("records_downloaded")] == "1234"


def test_append_row_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "deep" / "telemetry.csv"
    t = DownloadTelemetry(path)
    t.append_row(_row())
    assert path.exists()


def test_append_row_rejects_unknown_columns(tmp_path):
    t = DownloadTelemetry(tmp_path / "t.csv")
    with pytest.raises(ValueError, match="Unknown telemetry columns"):
        t.append_row({"chunk_date_utc": "2026-01-01", "bogus": "x"})


def test_append_row_rejects_invalid_status(tmp_path):
    t = DownloadTelemetry(tmp_path / "t.csv")
    with pytest.raises(ValueError, match="Invalid telemetry status"):
        t.append_row(_row(status="WHATEVER"))


def test_load_state_empty_when_no_file(tmp_path):
    t = DownloadTelemetry(tmp_path / "missing.csv")
    assert t.load_state() == {}


def test_load_state_returns_most_recent_row_per_date(tmp_path):
    t = DownloadTelemetry(tmp_path / "t.csv")

    # Two attempts on 2026-01-01: PENDING then FAILED (retry).
    t.append_row(
        _row(
            status=STATUS_PENDING,
            started_at_utc="2026-01-01T00:00:00.000000+00:00",
        )
    )
    t.append_row(
        _row(
            status=STATUS_FAILED,
            error_type="HTTPError",
            error_message="boom",
            started_at_utc="2026-01-01T00:05:00.000000+00:00",
            finished_at_utc="2026-01-01T00:05:30.000000+00:00",
        )
    )
    # One attempt on 2026-01-02: SKIPPED_NO_DATA.
    t.append_row(
        _row(
            chunk_date_utc="2026-01-02",
            window_start_utc="2026-01-02T00:00:00+00:00",
            window_end_utc="2026-01-03T00:00:00+00:00",
            status=STATUS_SKIPPED_NO_DATA,
            started_at_utc="2026-01-02T00:00:00.000000+00:00",
        )
    )

    state = t.load_state()

    assert set(state.keys()) == {date(2026, 1, 1), date(2026, 1, 2)}
    assert state[date(2026, 1, 1)].status == STATUS_FAILED
    assert state[date(2026, 1, 1)].error_message == "boom"
    assert state[date(2026, 1, 2)].status == STATUS_SKIPPED_NO_DATA


def test_load_state_skips_rows_with_unparseable_chunk_date(tmp_path):
    path = tmp_path / "t.csv"
    t = DownloadTelemetry(path)
    t.append_row(_row(chunk_date_utc="2026-01-01"))

    # Hand-write a junk row to simulate corruption.
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCHEMA)
        bad = {col: "" for col in SCHEMA}
        bad["chunk_date_utc"] = "not-a-date"
        bad["status"] = STATUS_DOWNLOADED
        bad["started_at_utc"] = "9999-01-01T00:00:00+00:00"
        writer.writerow(bad)

    state = t.load_state()
    assert set(state.keys()) == {date(2026, 1, 1)}


def test_iter_rows_returns_all_rows_in_order(tmp_path):
    t = DownloadTelemetry(tmp_path / "t.csv")
    t.append_row(_row(chunk_date_utc="2026-01-01"))
    t.append_row(_row(chunk_date_utc="2026-01-02"))

    rows = list(t.iter_rows())
    assert [r.chunk_date_utc for r in rows] == ["2026-01-01", "2026-01-02"]


def test_iter_rows_when_file_missing_yields_nothing(tmp_path):
    t = DownloadTelemetry(tmp_path / "missing.csv")
    assert list(t.iter_rows()) == []


def test_telemetry_row_to_dict_uses_schema_columns():
    row = _row()
    d = row.to_dict()
    assert set(d.keys()) == set(SCHEMA)


def test_utcnow_iso_returns_parseable_utc_timestamp():
    from datetime import datetime

    s = tm.utcnow_iso()
    parsed = datetime.fromisoformat(s)
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0
