"""Tests for ``swxsoc_reach.historical.telemetry``."""

from __future__ import annotations

import csv
from datetime import date

import pytest

from swxsoc_reach.historical import telemetry as tm
from swxsoc_reach.historical.telemetry import (
    HistoricalTelemetry,
    SCHEMA,
    STATUS_DOWNLOADED,
    STATUS_DOWNLOAD_PENDING,
    STATUS_FAILED,
    STATUS_SKIPPED_NO_DATA,
    TelemetryRow,
)


def _row(**overrides) -> TelemetryRow:
    base = dict(
        run_id="run-1",
        chunk_date_utc="2026-01-01",
        window_start_utc="2026-01-01T00:00:00+00:00",
        window_end_utc="2026-01-02T00:00:00+00:00",
        status=STATUS_DOWNLOAD_PENDING,
        sensor_id="REACH-1",
        descriptor="QUICKLOOK",
        data_level="raw",
        output_format="csv",
        started_at_utc="2026-01-01T00:00:00.000000+00:00",
    )
    base.update(overrides)
    return TelemetryRow(**base)


def test_append_row_writes_header_then_appends(tmp_path):
    path = tmp_path / "download_telemetry.csv"
    t = HistoricalTelemetry(path)

    t.append_row(_row(status=STATUS_DOWNLOAD_PENDING))
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
    assert rows[1][SCHEMA.index("status")] == STATUS_DOWNLOAD_PENDING
    assert rows[2][SCHEMA.index("status")] == STATUS_DOWNLOADED
    assert rows[2][SCHEMA.index("records_downloaded")] == "1234"


def test_append_row_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "deep" / "telemetry.csv"
    t = HistoricalTelemetry(path)
    t.append_row(_row())
    assert path.exists()


def test_append_row_rejects_unknown_columns(tmp_path):
    t = HistoricalTelemetry(tmp_path / "t.csv")
    with pytest.raises(ValueError, match="Unknown telemetry columns"):
        t.append_row({"chunk_date_utc": "2026-01-01", "bogus": "x"})


def test_append_row_rejects_invalid_status(tmp_path):
    t = HistoricalTelemetry(tmp_path / "t.csv")
    with pytest.raises(ValueError, match="Invalid telemetry status"):
        t.append_row(_row(status="WHATEVER"))


def test_load_state_empty_when_no_file(tmp_path):
    t = HistoricalTelemetry(tmp_path / "missing.csv")
    assert t.load_state() == {}


def test_load_state_returns_most_recent_row_per_date(tmp_path):
    t = HistoricalTelemetry(tmp_path / "t.csv")

    # Two attempts on 2026-01-01: PENDING then FAILED (retry).
    t.append_row(
        _row(
            status=STATUS_DOWNLOAD_PENDING,
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

    assert set(state.keys()) == {
        (date(2026, 1, 1), "raw"),
        (date(2026, 1, 2), "raw"),
    }
    assert state[(date(2026, 1, 1), "raw")][0].status == STATUS_FAILED
    assert state[(date(2026, 1, 1), "raw")][0].error_message == "boom"
    assert state[(date(2026, 1, 2), "raw")][0].status == STATUS_SKIPPED_NO_DATA


def test_load_state_skips_rows_with_unparseable_chunk_date(tmp_path):
    path = tmp_path / "t.csv"
    t = HistoricalTelemetry(path)
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
    assert set(state.keys()) == {(date(2026, 1, 1), "raw")}


def test_load_download_state_returns_latest_download_row_per_date(tmp_path):
    t = HistoricalTelemetry(tmp_path / "t.csv")
    t.append_row(_row(status=STATUS_DOWNLOAD_PENDING, data_level="raw"))
    t.append_row(_row(status=STATUS_DOWNLOADED, data_level="raw"))
    t.append_row(
        _row(
            status=STATUS_FAILED,
            data_level="l1c",
            cdf_path="/tmp/out.cdf",
            process_seconds="1.0",
        )
    )

    state = t.load_download_state()
    assert set(state.keys()) == {date(2026, 1, 1)}
    assert state[date(2026, 1, 1)].status == STATUS_DOWNLOADED


def test_iter_rows_returns_all_rows_in_order(tmp_path):
    t = HistoricalTelemetry(tmp_path / "t.csv")
    t.append_row(_row(chunk_date_utc="2026-01-01"))
    t.append_row(_row(chunk_date_utc="2026-01-02"))

    rows = list(t.iter_rows())
    assert [r.chunk_date_utc for r in rows] == ["2026-01-01", "2026-01-02"]


def test_iter_rows_when_file_missing_yields_nothing(tmp_path):
    t = HistoricalTelemetry(tmp_path / "missing.csv")
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


# ---------------------------------------------------------------------------
# Multi-level helpers
# ---------------------------------------------------------------------------


def test_valid_levels_from_swxsoc_config():
    levels = tm.valid_levels()
    assert "raw" in levels
    assert "l1c" in levels
    assert levels.index("raw") < levels.index("l1c")


def test_level_order_is_index_into_valid_levels():
    levels = tm.valid_levels()
    for i, name in enumerate(levels):
        assert tm.level_order(name) == i


def test_prior_level_returns_predecessor_or_none():
    levels = tm.valid_levels()
    assert tm.prior_level(levels[0]) is None
    assert tm.prior_level("l1c") == "raw"
    if "l2" in levels:
        assert tm.prior_level("l2") == "l1c"


def test_append_row_rejects_unknown_data_level(tmp_path):
    t = HistoricalTelemetry(tmp_path / "t.csv")
    with pytest.raises(ValueError, match="data_level"):
        t.append_row(_row(data_level="quantum"))


# ---------------------------------------------------------------------------
# Legacy schema synthesis & in-place upgrade
# ---------------------------------------------------------------------------


_LEGACY_SCHEMA = tuple(c for c in SCHEMA if c != "data_level")


def _write_legacy_csv(path, rows):
    """Write a CSV with the pre-data_level schema."""
    import csv as _csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=_LEGACY_SCHEMA)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _LEGACY_SCHEMA})


def test_load_state_synthesizes_raw_from_legacy_csv_path(tmp_path):
    path = tmp_path / "t.csv"
    _write_legacy_csv(
        path,
        [
            {
                "run_id": "old-1",
                "chunk_date_utc": "2026-01-01",
                "status": STATUS_DOWNLOADED,
                "csv_path": "/some/REACH-1_20260101T000000_20260102T000000.csv",
                "started_at_utc": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    state = HistoricalTelemetry(path).load_state()
    key = (date(2026, 1, 1), "raw")
    assert key in state
    assert state[key][0].status == STATUS_DOWNLOADED


def test_load_state_synthesizes_l1c_from_legacy_cdf_path(tmp_path):
    from swxsoc_reach.historical.telemetry import STATUS_PROCESSED

    path = tmp_path / "t.csv"
    _write_legacy_csv(
        path,
        [
            {
                "run_id": "old-2",
                "chunk_date_utc": "2026-01-01",
                "status": STATUS_PROCESSED,
                "cdf_path": "/out/reach_all_l1c_prelim_20260101T000000_v1.0.0.cdf",
                "started_at_utc": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    state = HistoricalTelemetry(path).load_state()
    assert (date(2026, 1, 1), "l1c") in state


def test_append_row_upgrades_legacy_schema_in_place(tmp_path):
    """Appending after a legacy CSV rewrites it to the new schema."""
    import csv as _csv

    path = tmp_path / "t.csv"
    _write_legacy_csv(
        path,
        [
            {
                "run_id": "old",
                "chunk_date_utc": "2026-01-01",
                "status": STATUS_DOWNLOADED,
                "csv_path": "/x.csv",
                "started_at_utc": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    HistoricalTelemetry(path).append_row(_row(chunk_date_utc="2026-01-02"))

    with open(path, newline="", encoding="utf-8") as fh:
        header = next(_csv.reader(fh))
    assert header == list(SCHEMA)
