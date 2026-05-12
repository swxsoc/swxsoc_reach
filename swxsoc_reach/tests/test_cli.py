"""Tests for the ``python -m swxsoc_reach`` CLI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from swxsoc_reach import __main__ as cli
from swxsoc_reach.historical.download_orchestrator import DownloadRunSummary


def _argv_download(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "download",
        "--start-date",
        "2026-01-01",
        "--end-date",
        "2026-01-02",
        "--output-dir",
        str(tmp_path / "out"),
        "--sensor-id",
        "REACH-1",
        *extra,
    ]


def test_parse_iso_date_valid():
    assert cli._parse_iso_date("2026-01-15") == date(2026, 1, 15)


def test_parse_iso_date_invalid():
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_iso_date("2026/01/15")


def test_build_parser_requires_subcommand():
    parser = cli._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_download_parser_minimum_args(tmp_path):
    parser = cli._build_parser()
    args = parser.parse_args(_argv_download(tmp_path))
    assert args.command == "download"
    assert args.start_date == date(2026, 1, 1)
    assert args.end_date == date(2026, 1, 2)
    assert args.output_dir == tmp_path / "out"
    assert args.telemetry_file is None
    assert args.sensor_id == "REACH-1"
    assert args.descriptor == "QUICKLOOK"
    assert args.output_format == "csv"
    assert args.retry_failed is False
    assert args.dry_run is False
    assert args.max_concurrent_requests == 4


def test_config_from_args_defaults_telemetry_to_output_dir(tmp_path):
    parser = cli._build_parser()
    args = parser.parse_args(_argv_download(tmp_path))
    config = cli._download_config_from_args(args, auth_token="Bearer x")
    assert config.telemetry_path == tmp_path / "out" / "download_telemetry.csv"
    assert config.auth_token == "Bearer x"


def test_config_from_args_honors_explicit_telemetry_file(tmp_path):
    custom = tmp_path / "elsewhere" / "t.csv"
    parser = cli._build_parser()
    args = parser.parse_args(_argv_download(tmp_path, "--telemetry-file", str(custom)))
    config = cli._download_config_from_args(args, auth_token="x")
    assert config.telemetry_path == custom


def test_main_download_dry_run_skips_auth_resolution(tmp_path, monkeypatch):
    """--dry-run must not call resolve_udl_auth (no network, no creds)."""

    def boom(**kwargs):
        raise AssertionError("resolve_udl_auth must not run for --dry-run")

    monkeypatch.setattr(cli, "resolve_udl_auth", boom)

    captured = {}

    def fake_run(config):
        captured["config"] = config
        return DownloadRunSummary(
            run_id="r-1",
            days_planned=2,
            days_attempted=0,
            days_downloaded=0,
            days_skipped_existing=0,
            days_skipped_no_data=0,
            days_failed=0,
        )

    monkeypatch.setattr(cli, "run_download", fake_run)

    rc = cli.main(_argv_download(tmp_path, "--dry-run"))
    assert rc == 0
    assert captured["config"].dry_run is True
    assert captured["config"].auth_token == ""


def test_main_download_resolves_auth_and_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli, "resolve_udl_auth", lambda region_name=None: "Basic from-aws"
    )

    captured = {}

    def fake_run(config):
        captured["config"] = config
        return DownloadRunSummary(
            run_id="r-1",
            days_planned=2,
            days_attempted=2,
            days_downloaded=2,
            days_skipped_existing=0,
            days_skipped_no_data=0,
            days_failed=0,
        )

    monkeypatch.setattr(cli, "run_download", fake_run)

    rc = cli.main(_argv_download(tmp_path))
    assert rc == 0
    assert captured["config"].auth_token == "Basic from-aws"
    assert captured["config"].sensor_id == "REACH-1"


def test_main_download_returns_2_when_auth_unavailable(tmp_path, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("BASICAUTH not set")

    monkeypatch.setattr(cli, "resolve_udl_auth", fail)
    monkeypatch.setattr(
        cli,
        "run_download",
        lambda config: pytest.fail("run_download must not be called"),
    )

    rc = cli.main(_argv_download(tmp_path))
    assert rc == 2


def test_main_download_returns_1_when_any_day_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "resolve_udl_auth", lambda region_name=None: "x")
    monkeypatch.setattr(
        cli,
        "run_download",
        lambda config: DownloadRunSummary(
            run_id="r-1",
            days_planned=2,
            days_attempted=2,
            days_downloaded=1,
            days_skipped_existing=0,
            days_skipped_no_data=0,
            days_failed=1,
        ),
    )

    rc = cli.main(_argv_download(tmp_path))
    assert rc == 1


def test_main_download_returns_2_when_dates_inverted(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli,
        "run_download",
        lambda config: pytest.fail("must not run with inverted dates"),
    )

    rc = cli.main(
        [
            "download",
            "--start-date",
            "2026-01-05",
            "--end-date",
            "2026-01-01",
            "--output-dir",
            str(tmp_path / "out"),
            "--dry-run",
        ]
    )
    assert rc == 2


def test_aimd_flags_propagate_to_config(tmp_path):
    parser = cli._build_parser()
    args = parser.parse_args(
        _argv_download(
            tmp_path,
            "--max-concurrent-requests",
            "8",
            "--initial-rate",
            "10.0",
            "--additive-increase",
            "2.0",
            "--multiplicative-decrease",
            "0.25",
            "--min-rate",
            "2.0",
            "--max-rate",
            "50.0",
        )
    )
    config = cli._download_config_from_args(args, auth_token="x")
    assert config.max_concurrent_requests == 8
    assert config.initial_rate == 10.0
    assert config.additive_increase == 2.0
    assert config.multiplicative_decrease == 0.25
    assert config.min_rate == 2.0
    assert config.max_rate == 50.0


# --- process subcommand ---


def _argv_process(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "process",
        "--start-date",
        "2026-01-01",
        "--end-date",
        "2026-01-02",
        "--input-dir",
        str(tmp_path / "in"),
        "--output-dir",
        str(tmp_path / "out"),
        "--sensor-id",
        "REACH-1",
        *extra,
    ]


def test_process_parser_minimum_args(tmp_path):
    parser = cli._build_parser()
    args = parser.parse_args(_argv_process(tmp_path))
    assert args.command == "process"
    assert args.input_dir == tmp_path / "in"
    assert args.output_dir == tmp_path / "out"
    assert args.upload_to_s3 is False
    assert args.s3_bucket is None
    assert args.telemetry_file is None


def test_process_config_telemetry_defaults_to_input_dir(tmp_path):
    parser = cli._build_parser()
    args = parser.parse_args(_argv_process(tmp_path))
    cfg = cli._process_config_from_args(args)
    assert cfg.telemetry_path == tmp_path / "in" / "download_telemetry.csv"


def test_process_upload_requires_bucket(tmp_path, monkeypatch):
    """--upload-to-s3 without --s3-bucket exits 2 via parser.error."""
    monkeypatch.setattr(
        cli,
        "run_process",
        lambda config: pytest.fail("must not run when bucket missing"),
    )
    with pytest.raises(SystemExit) as exc:
        cli.main(_argv_process(tmp_path, "--upload-to-s3"))
    assert exc.value.code == 2


def test_main_process_returns_1_on_failure(tmp_path, monkeypatch):
    from swxsoc_reach.historical.process_orchestrator import ProcessRunSummary

    monkeypatch.setattr(
        cli,
        "run_process",
        lambda config: ProcessRunSummary(
            run_id="r-1",
            days_planned=2,
            days_attempted=2,
            days_processed=1,
            days_uploaded=0,
            files_processed=1,
            files_uploaded=0,
            days_skipped_existing=0,
            days_skipped_no_input=0,
            days_failed=1,
        ),
    )
    rc = cli.main(_argv_process(tmp_path, "--dry-run"))
    assert rc == 1
