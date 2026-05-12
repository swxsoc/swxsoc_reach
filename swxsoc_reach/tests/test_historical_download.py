"""Tests for ``swxsoc_reach.historical.download_orchestrator``."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from swxsoc_reach.historical.download_orchestrator import (
    DownloadRunConfig,
    EXPECTED_RECORDS_ALL,
    EXPECTED_RECORDS_SINGLE,
    _decide_action,
    _iter_dates,
    run_download,
)
from swxsoc_reach.historical.telemetry import (
    HistoricalTelemetry,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_DOWNLOAD_PENDING,
    STATUS_SKIPPED_NO_DATA,
    TelemetryRow,
)


# --- helpers ---


def _config(tmp_path: Path, **overrides) -> DownloadRunConfig:
    base = dict(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
        output_dir=tmp_path / "out",
        telemetry_path=tmp_path / "out" / "download_telemetry.csv",
        sensor_id="REACH-1",
        descriptor="QUICKLOOK",
        output_format="csv",
        auth_token="Bearer test",
    )
    base.update(overrides)
    return DownloadRunConfig(**base)


def _make_csv_writer(records_per_day: int = 5):
    """Return a download_fn stub that writes a tiny CSV and returns the path."""

    def _fn(**kwargs):
        sensor_id = kwargs["sensor_id"]
        start_time = kwargs["start_time"]
        end_time = kwargs["end_time"]
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        # Filename matches the real downloader's convention closely enough
        # for tests; we just need a unique path per day.
        name = f"{sensor_id}_{start_time.isot}_{end_time.isot}.csv".replace(":", "")
        path = output_dir / name
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("col_a,col_b\n")
            for i in range(records_per_day):
                fh.write(f"v{i},w{i}\n")
        return path

    return _fn


# --- date / decision helpers ---


def test_iter_dates_inclusive():
    days = list(_iter_dates(date(2026, 1, 30), date(2026, 2, 2)))
    assert days == [
        date(2026, 1, 30),
        date(2026, 1, 31),
        date(2026, 2, 1),
        date(2026, 2, 2),
    ]


def test_iter_dates_single_day():
    assert list(_iter_dates(date(2026, 1, 1), date(2026, 1, 1))) == [date(2026, 1, 1)]


def test_iter_dates_rejects_inverted_range():
    with pytest.raises(ValueError):
        list(_iter_dates(date(2026, 1, 2), date(2026, 1, 1)))


@pytest.mark.parametrize(
    "prior_status,csv_exists,retry_failed,expected",
    [
        (None, False, False, "run"),
        (STATUS_DOWNLOAD_PENDING, False, False, "run"),
        (STATUS_DOWNLOADED, True, False, "skip_existing"),
        (STATUS_DOWNLOADED, False, False, "run"),
        (STATUS_SKIPPED_NO_DATA, False, False, "skip_terminal"),
        (STATUS_FAILED, False, False, "skip_failed"),
        (STATUS_FAILED, False, True, "run"),
    ],
)
def test_decide_action(tmp_path, prior_status, csv_exists, retry_failed, expected):
    if prior_status is None:
        prior = None
    else:
        csv_path = ""
        if csv_exists:
            p = tmp_path / "x.csv"
            p.write_text("a\n", encoding="utf-8")
            csv_path = str(p)
        prior = TelemetryRow(status=prior_status, csv_path=csv_path)

    assert _decide_action(date(2026, 1, 1), prior, retry_failed) == expected


# --- run_download integration ---


def test_run_download_single_day_writes_telemetry_and_artifact(tmp_path):
    cfg = _config(tmp_path)
    summary = run_download(cfg, download_fn=_make_csv_writer(records_per_day=10))

    assert summary.days_planned == 1
    assert summary.days_attempted == 1
    assert summary.days_downloaded == 1
    assert summary.days_failed == 0

    rows = list(HistoricalTelemetry(cfg.telemetry_path).iter_rows())
    statuses = [r.status for r in rows]
    assert statuses == [STATUS_DOWNLOAD_PENDING, STATUS_DOWNLOADED]
    final = rows[-1]
    assert final.data_level == "raw"
    assert final.records_downloaded == "10"
    assert final.expected_records == str(EXPECTED_RECORDS_SINGLE)
    assert final.csv_path
    assert Path(final.csv_path).exists()
    assert final.run_id == summary.run_id


def test_run_download_multi_day_inclusive_range(tmp_path):
    cfg = _config(tmp_path, start_date=date(2026, 1, 1), end_date=date(2026, 1, 3))
    summary = run_download(cfg, download_fn=_make_csv_writer())
    assert summary.days_downloaded == 3
    state = HistoricalTelemetry(cfg.telemetry_path).load_download_state()
    assert set(state.keys()) == {
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    }
    for row in state.values():
        assert row.status == STATUS_DOWNLOADED


def test_run_download_skips_already_downloaded_days(tmp_path):
    cfg = _config(tmp_path)
    run_download(cfg, download_fn=_make_csv_writer())

    # Re-run; downloader stub raises if it gets called.
    def boom(**kwargs):
        raise AssertionError("downloader must not be called for already-DOWNLOADED day")

    summary = run_download(cfg, download_fn=boom)
    assert summary.days_attempted == 0
    assert summary.days_skipped_existing == 1


def test_run_download_redownloads_when_csv_missing(tmp_path):
    cfg = _config(tmp_path)
    run_download(cfg, download_fn=_make_csv_writer())

    # Delete the CSV.
    state = HistoricalTelemetry(cfg.telemetry_path).load_download_state()
    Path(state[date(2026, 1, 1)].csv_path).unlink()

    summary = run_download(cfg, download_fn=_make_csv_writer())
    assert summary.days_downloaded == 1


def test_run_download_skipped_no_data_is_terminal(tmp_path):
    cfg = _config(tmp_path)

    def empty(**kwargs):
        raise ValueError("No records returned for sensor")

    summary = run_download(cfg, download_fn=empty)
    assert summary.days_skipped_no_data == 1

    # Re-run: should not call the downloader.
    def boom(**kwargs):
        raise AssertionError("downloader must not be called for SKIPPED_NO_DATA day")

    summary2 = run_download(cfg, download_fn=boom)
    assert summary2.days_attempted == 0
    assert summary2.days_skipped_no_data == 1


def test_run_download_failed_skipped_unless_retry(tmp_path):
    cfg = _config(tmp_path)

    def bad(**kwargs):
        raise RuntimeError("HTTP 500")

    run_download(cfg, download_fn=bad)

    # Default re-run: skip without invoking downloader.
    def boom(**kwargs):
        raise AssertionError("downloader must not be called without --retry-failed")

    s1 = run_download(cfg, download_fn=boom)
    assert s1.days_attempted == 0
    assert s1.days_failed == 1

    # With retry_failed: should invoke and succeed.
    cfg_retry = _config(tmp_path, retry_failed=True)
    s2 = run_download(cfg_retry, download_fn=_make_csv_writer())
    assert s2.days_downloaded == 1


def test_run_download_failure_classification(tmp_path):
    cfg = _config(tmp_path, start_date=date(2026, 1, 1), end_date=date(2026, 1, 2))

    def per_day(**kwargs):
        if kwargs["start_time"].isot.startswith("2026-01-01"):
            raise ValueError("No records returned")
        raise RuntimeError("connection reset")

    summary = run_download(cfg, download_fn=per_day)
    assert summary.days_skipped_no_data == 1
    assert summary.days_failed == 1

    state = HistoricalTelemetry(cfg.telemetry_path).load_download_state()
    assert state[date(2026, 1, 1)].status == STATUS_SKIPPED_NO_DATA
    assert state[date(2026, 1, 2)].status == STATUS_FAILED
    assert state[date(2026, 1, 2)].error_type == "RuntimeError"
    assert state[date(2026, 1, 2)].error_message == "connection reset"


def test_run_download_dry_run_writes_no_rows_no_files(tmp_path):
    cfg = _config(
        tmp_path,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        dry_run=True,
    )

    def boom(**kwargs):
        raise AssertionError("downloader must not be called in dry-run")

    summary = run_download(cfg, download_fn=boom)
    assert summary.days_planned == 3
    assert summary.days_attempted == 0
    assert not cfg.telemetry_path.exists()


def test_run_download_limit_days_counts_from_first_incomplete(tmp_path):
    # Day 1 already DOWNLOADED with artifact present.
    cfg_first = _config(tmp_path)
    run_download(cfg_first, download_fn=_make_csv_writer())

    cfg = _config(
        tmp_path,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        limit_days=2,
    )
    summary = run_download(cfg, download_fn=_make_csv_writer())
    # Day 1 is skip_existing (does not count); next 2 days run.
    assert summary.days_downloaded == 2
    assert summary.days_skipped_existing == 1

    state = HistoricalTelemetry(cfg.telemetry_path).load_download_state()
    assert set(state.keys()) == {
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    }


def test_run_download_uses_expected_records_for_all_sensor(tmp_path):
    cfg = _config(tmp_path, sensor_id="ALL")
    run_download(cfg, download_fn=_make_csv_writer())
    state = HistoricalTelemetry(cfg.telemetry_path).load_download_state()
    row = state[date(2026, 1, 1)]
    assert row.expected_records == str(EXPECTED_RECORDS_ALL)


def test_run_download_passes_aimd_and_window_args_through(tmp_path):
    cfg = _config(
        tmp_path,
        max_concurrent_requests=8,
        initial_rate=10.0,
        additive_increase=2.0,
        multiplicative_decrease=0.25,
        min_rate=2.0,
        max_rate=50.0,
    )

    captured = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return _make_csv_writer()(**kwargs)

    run_download(cfg, download_fn=capture)

    assert captured["max_concurrent_requests"] == 8
    assert captured["initial_rate"] == 10.0
    assert captured["additive_increase"] == 2.0
    assert captured["multiplicative_decrease"] == 0.25
    assert captured["min_rate"] == 2.0
    assert captured["max_rate"] == 50.0
    assert captured["auth_token"] == "Bearer test"
    # Day boundaries: 00:00:00 → next 00:00:00 (exclusive end)
    assert captured["start_time"].isot.startswith("2026-01-01T00:00:00")
    assert captured["end_time"].isot.startswith("2026-01-02T00:00:00")


def test_run_download_ignores_process_rows_when_resuming(tmp_path):
    cfg = _config(tmp_path)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    telemetry = HistoricalTelemetry(cfg.telemetry_path)
    telemetry.append_row(
        TelemetryRow(
            run_id="raw-r1",
            chunk_date_utc="2026-01-01",
            status=STATUS_FAILED,
            sensor_id=cfg.sensor_id,
            descriptor=cfg.descriptor,
            data_level="raw",
            output_format=cfg.output_format,
            started_at_utc="2026-01-01T00:00:00+00:00",
            finished_at_utc="2026-01-01T00:01:00+00:00",
            error_type="RuntimeError",
            error_message="download failed",
        )
    )
    telemetry.append_row(
        TelemetryRow(
            run_id="l1c-r1",
            chunk_date_utc="2026-01-01",
            status="PROCESSED",
            sensor_id=cfg.sensor_id,
            descriptor=cfg.descriptor,
            data_level="l1c",
            output_format=cfg.output_format,
            cdf_path=str(tmp_path / "out" / "x.cdf"),
            started_at_utc="2026-01-01T00:02:00+00:00",
            finished_at_utc="2026-01-01T00:03:00+00:00",
        )
    )

    cfg_retry = _config(tmp_path, retry_failed=True)
    summary = run_download(cfg_retry, download_fn=_make_csv_writer())
    assert summary.days_downloaded == 1


def test_run_download_legacy_csv_without_data_level_column(tmp_path):
    cfg = _config(tmp_path)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    legacy_cols = [
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
        "process_seconds",
        "cdf_size_mb",
        "upload_seconds",
        "s3_bucket",
        "s3_key",
        "csv_path",
        "sensor_id",
        "descriptor",
        "output_format",
        "error_type",
        "error_message",
        "started_at_utc",
        "finished_at_utc",
    ]
    legacy_row = {
        "run_id": "legacy-r1",
        "chunk_date_utc": "2026-01-01",
        "window_start_utc": "2026-01-01T00:00:00+00:00",
        "window_end_utc": "2026-01-02T00:00:00+00:00",
        "status": STATUS_FAILED,
        "sensor_id": cfg.sensor_id,
        "descriptor": cfg.descriptor,
        "output_format": cfg.output_format,
        "error_type": "RuntimeError",
        "error_message": "legacy failed",
        "started_at_utc": "2026-01-01T00:00:00+00:00",
        "finished_at_utc": "2026-01-01T00:01:00+00:00",
    }

    with open(cfg.telemetry_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=legacy_cols)
        writer.writeheader()
        writer.writerow(legacy_row)

    summary = run_download(_config(tmp_path, retry_failed=True), download_fn=_make_csv_writer())
    assert summary.days_downloaded == 1

    rows = list(HistoricalTelemetry(cfg.telemetry_path).iter_rows())
    assert rows[-1].status == STATUS_DOWNLOADED
    assert rows[-1].data_level == "raw"
