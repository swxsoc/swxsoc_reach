"""Multi-level (--target-level) and orphan-pending integration tests for
``swxsoc_reach.historical.process_orchestrator``.

Split from ``test_historical_process.py`` to keep that file focused on the
single-level (L1C) happy paths.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from swxsoc_reach.historical.process_orchestrator import (
    ProcessRunConfig,
    run_process,
)
from swxsoc_reach.historical.telemetry import (
    HistoricalTelemetry,
    STATUS_PROCESS_PENDING,
    STATUS_PROCESSED,
    STATUS_SKIPPED_NO_INPUT,
    TelemetryRow,
)


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


def _make_csv(input_dir: Path, day: date, sensor_id: str = "REACH-1") -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    sensor_prefix = "REACH-ALL" if sensor_id.upper() == "ALL" else sensor_id
    start_str = day.strftime("%Y%m%dT000000")
    next_day = date.fromordinal(day.toordinal() + 1)
    end_str = next_day.strftime("%Y%m%dT000000")
    name = f"{sensor_prefix}_{start_str}_{end_str}.csv"
    p = input_dir / name
    p.write_text("col_a,col_b\nv0,w0\n", encoding="utf-8")
    return p


def _make_l1c_process_fn():
    def _fn(csv_path: Path):
        cdf = Path.cwd() / (csv_path.stem + ".cdf")
        cdf.write_bytes(b"FAKE_CDF" * 32)
        return [cdf]

    return _fn


_L1C_CDF_NAME = "reach_all_l1c_prelim_20260101T000000_v1.0.0.cdf"


def _seed_l1c_state(cfg: ProcessRunConfig) -> Path:
    """Pre-create an L1C CDF + matching telemetry row for 2026-01-01."""
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cdf = cfg.output_dir / _L1C_CDF_NAME
    cdf.write_bytes(b"FAKE_L1C" * 32)
    telemetry = HistoricalTelemetry(cfg.telemetry_path)
    telemetry.append_row(
        TelemetryRow(
            run_id="seed",
            chunk_date_utc="2026-01-01",
            status=STATUS_PROCESSED,
            sensor_id=cfg.sensor_id,
            descriptor=cfg.descriptor,
            data_level="l1c",
            output_format=cfg.output_format,
            cdf_path=str(cdf),
            cdf_size_mb="0.001",
            process_seconds="0.5",
            started_at_utc="2026-01-01T00:00:00+00:00",
            finished_at_utc="2026-01-01T00:00:01+00:00",
        )
    )
    return cdf


def _make_l2_process_fn(n_outputs: int = 2):
    def _fn(input_path: Path):
        produced = []
        for i in range(n_outputs):
            flavor = chr(ord("u") + i)
            out = Path.cwd() / f"reach_flavor-{flavor}_l2_prelim_20260101T000000_v1.0.0.cdf"
            out.write_bytes(b"FAKE_L2_CDF" * 16)
            produced.append(out)
        return produced

    return _fn


def test_run_process_target_level_l2_writes_row_per_output(tmp_path):
    cfg = _config(tmp_path, target_level="l2")
    seeded = _seed_l1c_state(cfg)

    captured_inputs: list[Path] = []

    def process_fn(input_path):
        captured_inputs.append(input_path)
        return _make_l2_process_fn(n_outputs=2)(input_path)

    summary = run_process(cfg, process_fn=process_fn)

    assert summary.days_processed == 1
    assert summary.files_processed == 2
    assert captured_inputs == [seeded]

    state = HistoricalTelemetry(cfg.telemetry_path).load_state()
    l2_rows = state[(date(2026, 1, 1), "l2")]
    processed = [r for r in l2_rows if r.status == STATUS_PROCESSED]
    assert len(processed) == 2
    for r in processed:
        assert r.data_level == "l2"
        assert r.cdf_path.endswith(".cdf")


def test_run_process_target_level_l2_skip_existing_on_rerun(tmp_path):
    cfg = _config(tmp_path, target_level="l2")
    _seed_l1c_state(cfg)
    run_process(cfg, process_fn=_make_l2_process_fn(n_outputs=2))

    def boom(input_path):
        raise AssertionError("must not reprocess a complete L2 day")

    summary = run_process(cfg, process_fn=boom)
    assert summary.days_skipped_existing == 1


def test_run_process_target_level_l2_no_prior_l1c_skips(tmp_path):
    cfg = _config(tmp_path, target_level="l2")
    summary = run_process(cfg, process_fn=_make_l2_process_fn())
    assert summary.days_skipped_no_input == 1
    state = HistoricalTelemetry(cfg.telemetry_path).load_state()
    assert state[(date(2026, 1, 1), "l2")][0].status == STATUS_SKIPPED_NO_INPUT


def test_run_process_orphan_process_pending_reprocesses(tmp_path):
    """A bare PROCESS_PENDING row with no finalized successor is reprocessed."""
    cfg = _config(tmp_path)
    _make_csv(cfg.input_dir, date(2026, 1, 1))
    telemetry = HistoricalTelemetry(cfg.telemetry_path)
    telemetry.append_row(
        TelemetryRow(
            run_id="crashed",
            chunk_date_utc="2026-01-01",
            status=STATUS_PROCESS_PENDING,
            sensor_id=cfg.sensor_id,
            descriptor=cfg.descriptor,
            data_level="l1c",
            output_format=cfg.output_format,
            started_at_utc="2026-01-01T00:00:00+00:00",
        )
    )

    summary = run_process(cfg, process_fn=_make_l1c_process_fn())
    assert summary.days_processed == 1
    final = telemetry.load_state()[(date(2026, 1, 1), "l1c")]
    assert any(r.status == STATUS_PROCESSED for r in final)
