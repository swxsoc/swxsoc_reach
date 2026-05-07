"""Tests for ``swxsoc_reach.historical.process_orchestrator``.

Stubs ``process_fn`` (writes a fake CDF) and ``upload_fn`` (returns a
fake S3 key) so we never touch real CDF tooling, real boto3, or
sdc_aws_utils.
"""

from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path

import pytest

from swxsoc_reach.historical.process_orchestrator import (
    ProcessRunConfig,
    _decide_process_action,
    _match_csv_for_date,
    _relocate_to_nested_layout,
    run_process,
)
from swxsoc_reach.historical.telemetry import (
    HistoricalTelemetry,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_PROCESS_PENDING,
    STATUS_PROCESSED,
    STATUS_SKIPPED_NO_INPUT,
    STATUS_UPLOAD_PENDING,
    STATUS_UPLOADED,
    TelemetryRow,
)


# --- helpers ---


def _make_csv(input_dir: Path, day: date, sensor_id: str = "REACH-1") -> Path:
    """Write a fake Phase 1 CSV with the canonical naming pattern."""
    input_dir.mkdir(parents=True, exist_ok=True)
    sensor_prefix = "REACH-ALL" if sensor_id.upper() == "ALL" else sensor_id
    start_str = day.strftime("%Y%m%dT000000")
    end_day = day.replace(day=day.day) + (date.fromordinal(day.toordinal() + 1) - day)
    end_str = end_day.strftime("%Y%m%dT000000")
    name = f"{sensor_prefix}_{start_str}_{end_str}.csv"
    p = input_dir / name
    p.write_text("col_a,col_b\nv0,w0\n", encoding="utf-8")
    return p


def _config(tmp_path: Path, **overrides) -> ProcessRunConfig:
    base = dict(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
        input_dir=tmp_path / "in",
        output_dir=tmp_path / "out",
        telemetry_path=tmp_path / "in" / "download_telemetry.csv",
        sensor_id="REACH-1",
        descriptor="QUICKLOOK",
        output_format="csv",
    )
    base.update(overrides)
    return ProcessRunConfig(**base)


def _make_process_fn(records_per_day: int = 1):
    """Return a process_fn stub that writes a fake CDF in cwd."""

    def _fn(csv_path: Path):
        # Mirrors process_file's contract: writes to cwd, returns list[Path].
        cdf_name = csv_path.stem + ".cdf"
        cdf = Path.cwd() / cdf_name
        cdf.write_bytes(b"FAKE_CDF" * 32)
        return [cdf]

    return _fn


def _make_upload_fn(key_prefix: str = "l1c/2026/01/"):
    def _fn(cdf_path, *, destination_bucket):
        return destination_bucket, f"{key_prefix}{cdf_path.name}"

    return _fn


# --- helper coverage ---


def test_match_csv_for_date(tmp_path):
    in_dir = tmp_path / "in"
    p = _make_csv(in_dir, date(2026, 1, 1), sensor_id="REACH-1")
    assert _match_csv_for_date(in_dir, date(2026, 1, 1), "REACH-1", "csv") == p
    assert _match_csv_for_date(in_dir, date(2026, 1, 2), "REACH-1", "csv") is None


def test_match_csv_for_date_all_sensor(tmp_path):
    in_dir = tmp_path / "in"
    p = _make_csv(in_dir, date(2026, 1, 1), sensor_id="ALL")
    assert _match_csv_for_date(in_dir, date(2026, 1, 1), "ALL", "csv") == p


@pytest.mark.parametrize(
    "prior_status,upload_to_s3,csv_available,retry_failed,cdf_exists,expected",
    [
        # No prior row
        (None, False, True, False, False, "run_process"),
        (None, False, False, False, False, "skip_no_input"),
        # PROCESSED, local-only
        (STATUS_PROCESSED, False, True, False, True, "skip_existing"),
        (STATUS_PROCESSED, False, True, False, False, "run_process"),
        # PROCESSED, upload mode
        (STATUS_PROCESSED, True, True, False, True, "run_upload_only"),
        (STATUS_PROCESSED, True, True, False, False, "run_process"),
        # UPLOADED is always terminal
        (STATUS_UPLOADED, True, True, False, True, "skip_existing"),
        (STATUS_UPLOADED, False, True, False, True, "skip_existing"),
        # UPLOAD_PENDING
        (STATUS_UPLOAD_PENDING, True, True, False, True, "run_upload_only"),
        (STATUS_UPLOAD_PENDING, True, True, False, False, "run_process"),
        # PROCESS_PENDING
        (STATUS_PROCESS_PENDING, True, True, False, False, "run_process"),
        (STATUS_PROCESS_PENDING, True, False, False, False, "skip_no_input"),
        # FAILED
        (STATUS_FAILED, False, True, False, False, "skip_failed"),
        (STATUS_FAILED, False, True, True, False, "run_process"),
        # SKIPPED_NO_INPUT
        (STATUS_SKIPPED_NO_INPUT, False, False, False, False, "skip_terminal"),
        (STATUS_SKIPPED_NO_INPUT, False, True, False, False, "run_process"),
        # Phase 1 statuses are treated as no prior process row
        (STATUS_DOWNLOADED, False, True, False, False, "run_process"),
    ],
)
def test_decide_process_action(
    tmp_path,
    prior_status,
    upload_to_s3,
    csv_available,
    retry_failed,
    cdf_exists,
    expected,
):
    if prior_status is None:
        prior = None
    else:
        cdf_path = ""
        if cdf_exists:
            p = tmp_path / "x.cdf"
            p.write_bytes(b"x")
            cdf_path = str(p)
        prior = TelemetryRow(status=prior_status, cdf_path=cdf_path)
    assert (
        _decide_process_action(
            prior,
            upload_to_s3=upload_to_s3,
            csv_available=csv_available,
            retry_failed=retry_failed,
        )
        == expected
    )


# --- run_process integration ---


def test_run_process_single_day_local_only(tmp_path):
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))

    summary = run_process(cfg, process_fn=_make_process_fn())

    assert summary.days_processed == 1
    assert summary.days_uploaded == 0
    assert summary.days_failed == 0

    rows = list(HistoricalTelemetry(cfg.telemetry_path).iter_rows())
    statuses = [r.status for r in rows]
    assert statuses == [STATUS_PROCESS_PENDING, STATUS_PROCESSED]
    final = rows[-1]
    assert final.cdf_path
    assert Path(final.cdf_path).exists()
    assert Path(final.cdf_path).parent == cfg.output_dir
    assert final.cdf_size_mb
    assert final.run_id == summary.run_id


def test_run_process_no_input_records_skipped(tmp_path):
    cfg = _config(tmp_path)
    cfg.input_dir.mkdir(parents=True)

    summary = run_process(cfg, process_fn=_make_process_fn())
    assert summary.days_skipped_no_input == 1
    assert summary.days_processed == 0

    state = HistoricalTelemetry(cfg.telemetry_path).load_state()
    assert state[date(2026, 1, 1)].status == STATUS_SKIPPED_NO_INPUT


def test_run_process_skips_already_processed_local_only(tmp_path):
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))
    run_process(cfg, process_fn=_make_process_fn())

    def boom(csv_path):
        raise AssertionError("process_fn must not be called for completed day")

    summary = run_process(cfg, process_fn=boom)
    assert summary.days_skipped_existing == 1
    assert summary.days_attempted == 0


def test_run_process_reprocesses_when_cdf_missing(tmp_path):
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))
    run_process(cfg, process_fn=_make_process_fn())

    state = HistoricalTelemetry(cfg.telemetry_path).load_state()
    Path(state[date(2026, 1, 1)].cdf_path).unlink()

    summary = run_process(cfg, process_fn=_make_process_fn())
    assert summary.days_processed == 1


def test_run_process_with_s3_upload(tmp_path):
    cfg = _config(tmp_path, upload_to_s3=True, s3_bucket="my-bucket")
    _make_csv(cfg.input_dir, date(2026, 1, 1))

    summary = run_process(
        cfg,
        process_fn=_make_process_fn(),
        upload_fn=_make_upload_fn(),
    )

    assert summary.days_processed == 1
    assert summary.days_uploaded == 1

    rows = list(HistoricalTelemetry(cfg.telemetry_path).iter_rows())
    statuses = [r.status for r in rows]
    assert statuses == [
        STATUS_PROCESS_PENDING,
        STATUS_PROCESSED,
        STATUS_UPLOAD_PENDING,
        STATUS_UPLOADED,
    ]
    final = rows[-1]
    assert final.s3_bucket == "my-bucket"
    assert final.s3_key.endswith(".cdf")
    assert final.upload_seconds


def test_run_process_upload_only_resume_from_processed(tmp_path):
    """Local-only run produces PROCESSED; rerun with --upload-to-s3 should
    skip processing and only upload."""
    cfg_local = _config(tmp_path)
    _make_csv(cfg_local.input_dir, date(2026, 1, 1))
    run_process(cfg_local, process_fn=_make_process_fn())

    cfg_upload = _config(tmp_path, upload_to_s3=True, s3_bucket="my-bucket")

    def must_not_process(csv_path):
        raise AssertionError("process_fn must not be called when re-uploading")

    summary = run_process(
        cfg_upload, process_fn=must_not_process, upload_fn=_make_upload_fn()
    )
    assert summary.days_processed == 0
    assert summary.days_uploaded == 1


def test_run_process_uploaded_is_terminal(tmp_path):
    cfg = _config(tmp_path, upload_to_s3=True, s3_bucket="b")
    _make_csv(cfg.input_dir, date(2026, 1, 1))
    run_process(cfg, process_fn=_make_process_fn(), upload_fn=_make_upload_fn())

    def boom(*a, **kw):
        raise AssertionError("must not run again after UPLOADED")

    summary = run_process(cfg, process_fn=boom, upload_fn=boom)
    assert summary.days_skipped_existing == 1


def test_run_process_failure_at_process_stage(tmp_path):
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))

    def bad(csv_path):
        raise RuntimeError("boom")

    summary = run_process(cfg, process_fn=bad)
    assert summary.days_failed == 1

    state = HistoricalTelemetry(cfg.telemetry_path).load_state()
    row = state[date(2026, 1, 1)]
    assert row.status == STATUS_FAILED
    assert row.error_type == "RuntimeError"
    assert row.error_message == "boom"


def test_run_process_failure_at_upload_stage(tmp_path):
    cfg = _config(tmp_path, upload_to_s3=True, s3_bucket="b")
    _make_csv(cfg.input_dir, date(2026, 1, 1))

    def bad_upload(cdf_path, *, destination_bucket):
        raise ConnectionError("net down")

    summary = run_process(cfg, process_fn=_make_process_fn(), upload_fn=bad_upload)
    assert summary.days_processed == 1
    assert summary.days_failed == 1

    rows = list(HistoricalTelemetry(cfg.telemetry_path).iter_rows())
    statuses = [r.status for r in rows]
    assert statuses[-2:] == [STATUS_UPLOAD_PENDING, STATUS_FAILED]
    assert rows[-1].error_type == "ConnectionError"


def test_run_process_failed_skip_unless_retry(tmp_path):
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))
    run_process(
        cfg, process_fn=lambda csv_path: (_ for _ in ()).throw(RuntimeError("x"))
    )

    def boom(csv_path):
        raise AssertionError("must not run without --retry-failed")

    s1 = run_process(cfg, process_fn=boom)
    assert s1.days_failed == 1
    assert s1.days_attempted == 0

    cfg_retry = _config(tmp_path, retry_failed=True)
    s2 = run_process(cfg_retry, process_fn=_make_process_fn())
    assert s2.days_processed == 1


def test_run_process_dry_run_no_writes(tmp_path):
    cfg = _config(
        tmp_path,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        dry_run=True,
    )
    cfg.input_dir.mkdir(parents=True)
    _make_csv(cfg.input_dir, date(2026, 1, 1))

    def boom(csv_path):
        raise AssertionError("must not run in dry-run")

    summary = run_process(cfg, process_fn=boom)
    assert summary.days_planned == 3
    assert summary.days_attempted == 0
    assert not cfg.telemetry_path.exists()


def test_run_process_limit_days_after_resume(tmp_path):
    # Day 1 already PROCESSED, in local-only mode (terminal).
    cfg_first = _config(tmp_path)
    _make_csv(cfg_first.input_dir, date(2026, 1, 1))
    run_process(cfg_first, process_fn=_make_process_fn())

    # Make CSVs for days 2, 3, 4, 5
    for d in (date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5)):
        _make_csv(cfg_first.input_dir, d)

    cfg = _config(
        tmp_path,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        limit_days=2,
    )
    summary = run_process(cfg, process_fn=_make_process_fn())
    assert summary.days_skipped_existing == 1
    assert summary.days_processed == 2


def test_run_process_upload_to_s3_requires_bucket():
    cfg = ProcessRunConfig(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
        input_dir=Path("/tmp/in"),
        output_dir=Path("/tmp/out"),
        telemetry_path=Path("/tmp/t.csv"),
        upload_to_s3=True,
        s3_bucket=None,
    )
    with pytest.raises(ValueError, match="s3_bucket"):
        run_process(cfg, process_fn=_make_process_fn())


# ---------------------------------------------------------------------------
# _relocate_to_nested_layout unit tests
# ---------------------------------------------------------------------------

# CDF filename that parse_science_filename can handle (matches real REACH output).
_REACH_CDF = "reach_all_l1c_prelim_20260101T000000_v1.0.0.cdf"
_NESTED_KEY = "l1c/prelim/2026/01/01/" + _REACH_CDF


def _fake_sdc_modules(nested_key: str) -> tuple[types.ModuleType, types.ModuleType]:
    """Return fake (sdc_aws_utils, sdc_aws_utils.aws) module objects."""
    fake_aws = types.ModuleType("sdc_aws_utils.aws")
    fake_aws.create_s3_file_key = lambda parser, filename: nested_key
    fake_sdc = types.ModuleType("sdc_aws_utils")
    fake_sdc.aws = fake_aws
    return fake_sdc, fake_aws


def _fake_swxsoc_modules() -> tuple[
    types.ModuleType, types.ModuleType, types.ModuleType
]:
    """Return fake (swxsoc, swxsoc.util, swxsoc.util.util) module objects."""
    sentinel_parser = object()
    fake_util_util = types.ModuleType("swxsoc.util.util")
    fake_util_util.parse_science_filename = sentinel_parser
    fake_util = types.ModuleType("swxsoc.util")
    fake_util.util = fake_util_util
    fake_swxsoc = types.ModuleType("swxsoc")
    fake_swxsoc.util = fake_util
    return fake_swxsoc, fake_util, fake_util_util


def test_relocate_to_nested_layout_success(tmp_path, monkeypatch):
    """When sdc_aws_utils is importable and key computation succeeds, the CDF
    is moved into the nested subdirectory under output_dir."""
    flat = tmp_path / _REACH_CDF
    flat.write_bytes(b"FAKE_CDF" * 32)
    output_dir = tmp_path  # same root; nested dest will be a subdirectory

    fake_sdc, fake_aws = _fake_sdc_modules(_NESTED_KEY)
    fake_swxsoc, fake_util, fake_util_util = _fake_swxsoc_modules()

    monkeypatch.setitem(sys.modules, "sdc_aws_utils", fake_sdc)
    monkeypatch.setitem(sys.modules, "sdc_aws_utils.aws", fake_aws)
    monkeypatch.setitem(sys.modules, "swxsoc", fake_swxsoc)
    monkeypatch.setitem(sys.modules, "swxsoc.util", fake_util)
    monkeypatch.setitem(sys.modules, "swxsoc.util.util", fake_util_util)

    result = _relocate_to_nested_layout(flat, output_dir)

    expected = output_dir / _NESTED_KEY
    assert result == expected
    assert expected.exists()
    assert not flat.exists()  # moved, not copied


def test_relocate_to_nested_layout_import_error(tmp_path, monkeypatch):
    """When sdc_aws_utils is not importable, the flat path is returned unchanged."""
    flat = tmp_path / _REACH_CDF
    flat.write_bytes(b"FAKE_CDF" * 32)

    monkeypatch.setitem(sys.modules, "sdc_aws_utils", None)
    monkeypatch.setitem(sys.modules, "sdc_aws_utils.aws", None)

    result = _relocate_to_nested_layout(flat, tmp_path)

    assert result == flat
    assert flat.exists()


def test_relocate_to_nested_layout_key_computation_error(tmp_path, monkeypatch):
    """When create_s3_file_key raises, the flat path is returned unchanged."""
    flat = tmp_path / _REACH_CDF
    flat.write_bytes(b"FAKE_CDF" * 32)

    def _boom(parser, filename):
        raise ValueError("bad filename")

    fake_aws = types.ModuleType("sdc_aws_utils.aws")
    fake_aws.create_s3_file_key = _boom
    fake_sdc = types.ModuleType("sdc_aws_utils")
    fake_sdc.aws = fake_aws
    fake_swxsoc, fake_util, fake_util_util = _fake_swxsoc_modules()

    monkeypatch.setitem(sys.modules, "sdc_aws_utils", fake_sdc)
    monkeypatch.setitem(sys.modules, "sdc_aws_utils.aws", fake_aws)
    monkeypatch.setitem(sys.modules, "swxsoc", fake_swxsoc)
    monkeypatch.setitem(sys.modules, "swxsoc.util", fake_util)
    monkeypatch.setitem(sys.modules, "swxsoc.util.util", fake_util_util)

    result = _relocate_to_nested_layout(flat, tmp_path)

    assert result == flat
    assert flat.exists()


def test_relocate_to_nested_layout_already_at_dest(tmp_path, monkeypatch):
    """When the computed dest equals the flat path, no move occurs."""
    # Create a file already sitting at the nested path.
    nested_dir = tmp_path / "l1c" / "prelim" / "2026" / "01" / "01"
    nested_dir.mkdir(parents=True)
    already_nested = nested_dir / _REACH_CDF
    already_nested.write_bytes(b"FAKE_CDF" * 32)

    # Tell the fake key builder to return the *same* relative path.
    full_nested_key = "l1c/prelim/2026/01/01/" + _REACH_CDF
    fake_aws = types.ModuleType("sdc_aws_utils.aws")
    fake_aws.create_s3_file_key = lambda parser, filename: full_nested_key
    fake_sdc = types.ModuleType("sdc_aws_utils")
    fake_sdc.aws = fake_aws
    fake_swxsoc, fake_util, fake_util_util = _fake_swxsoc_modules()

    monkeypatch.setitem(sys.modules, "sdc_aws_utils", fake_sdc)
    monkeypatch.setitem(sys.modules, "sdc_aws_utils.aws", fake_aws)
    monkeypatch.setitem(sys.modules, "swxsoc", fake_swxsoc)
    monkeypatch.setitem(sys.modules, "swxsoc.util", fake_util)
    monkeypatch.setitem(sys.modules, "swxsoc.util.util", fake_util_util)

    result = _relocate_to_nested_layout(already_nested, tmp_path)

    assert result == already_nested
    assert already_nested.exists()


# ---------------------------------------------------------------------------
# run_process integration: nested layout
# ---------------------------------------------------------------------------


def _make_process_fn_reach(cdf_name: str = _REACH_CDF):
    """Like _make_process_fn but writes a properly-named REACH CDF."""

    def _fn(csv_path: Path):
        cdf = Path.cwd() / cdf_name
        cdf.write_bytes(b"FAKE_CDF" * 32)
        return [cdf]

    return _fn


def test_run_process_nested_layout_integration(tmp_path, monkeypatch):
    """When sdc_aws_utils is importable, process_fn output is relocated
    to the nested path and telemetry records the nested cdf_path."""
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))

    fake_sdc, fake_aws = _fake_sdc_modules(_NESTED_KEY)
    fake_swxsoc, fake_util, fake_util_util = _fake_swxsoc_modules()

    monkeypatch.setitem(sys.modules, "sdc_aws_utils", fake_sdc)
    monkeypatch.setitem(sys.modules, "sdc_aws_utils.aws", fake_aws)
    monkeypatch.setitem(sys.modules, "swxsoc", fake_swxsoc)
    monkeypatch.setitem(sys.modules, "swxsoc.util", fake_util)
    monkeypatch.setitem(sys.modules, "swxsoc.util.util", fake_util_util)

    summary = run_process(cfg, process_fn=_make_process_fn_reach())
    assert summary.days_processed == 1
    assert summary.days_failed == 0

    from swxsoc_reach.historical.telemetry import HistoricalTelemetry

    state = HistoricalTelemetry(cfg.telemetry_path).load_state()
    row = state[date(2026, 1, 1)]
    assert row.status == "PROCESSED"

    expected_path = cfg.output_dir / _NESTED_KEY
    assert row.cdf_path == str(expected_path)
    assert expected_path.exists()
    # flat location should no longer exist
    assert not (cfg.output_dir / _REACH_CDF).exists()


def test_run_process_nested_layout_skip_existing_on_rerun(tmp_path, monkeypatch):
    """After a nested-layout run, rerunning skips the day (already complete)."""
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))

    fake_sdc, fake_aws = _fake_sdc_modules(_NESTED_KEY)
    fake_swxsoc, fake_util, fake_util_util = _fake_swxsoc_modules()

    for key, val in [
        ("sdc_aws_utils", fake_sdc),
        ("sdc_aws_utils.aws", fake_aws),
        ("swxsoc", fake_swxsoc),
        ("swxsoc.util", fake_util),
        ("swxsoc.util.util", fake_util_util),
    ]:
        monkeypatch.setitem(sys.modules, key, val)

    run_process(cfg, process_fn=_make_process_fn_reach())

    def boom(csv_path):
        raise AssertionError("must not reprocess a completed nested-layout day")

    summary = run_process(cfg, process_fn=boom)
    assert summary.days_skipped_existing == 1
    assert summary.days_attempted == 0


def test_run_process_nested_layout_upload_only(tmp_path, monkeypatch):
    """Nested-layout CDF path flows into upload_fn correctly."""
    cfg_local = _config(tmp_path)
    _make_csv(cfg_local.input_dir, date(2026, 1, 1))

    fake_sdc, fake_aws = _fake_sdc_modules(_NESTED_KEY)
    fake_swxsoc, fake_util, fake_util_util = _fake_swxsoc_modules()

    for key, val in [
        ("sdc_aws_utils", fake_sdc),
        ("sdc_aws_utils.aws", fake_aws),
        ("swxsoc", fake_swxsoc),
        ("swxsoc.util", fake_util),
        ("swxsoc.util.util", fake_util_util),
    ]:
        monkeypatch.setitem(sys.modules, key, val)

    run_process(cfg_local, process_fn=_make_process_fn_reach())

    cfg_upload = _config(tmp_path, upload_to_s3=True, s3_bucket="my-bucket")

    received_paths: list[Path] = []

    def capturing_upload_fn(cdf_path, *, destination_bucket):
        received_paths.append(cdf_path)
        return destination_bucket, f"l1c/prelim/2026/01/01/{cdf_path.name}"

    def must_not_process(csv_path):
        raise AssertionError("process_fn must not run for upload-only resume")

    summary = run_process(
        cfg_upload,
        process_fn=must_not_process,
        upload_fn=capturing_upload_fn,
    )

    assert summary.days_uploaded == 1
    assert len(received_paths) == 1
    assert received_paths[0] == cfg_upload.output_dir / _NESTED_KEY
