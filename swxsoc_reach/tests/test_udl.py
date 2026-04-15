import csv
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from astropy.time import Time

import swxsoc_reach.net.udl as udl
from swxsoc_reach.net.udl import AdaptiveRateController


@pytest.mark.parametrize(
    "time_value,expected",
    [
        (
            Time("2026-01-02T03:04:05", format="isot", scale="utc"),
            "2026-01-02T03:04:05.000Z",
        ),
        (
            Time("2026-12-31T23:59:59", format="isot", scale="utc"),
            "2026-12-31T23:59:59.000Z",
        ),
    ],
)
def test_format_udl_timestamp(time_value, expected):
    assert udl.format_udl_timestamp(time_value) == expected


@pytest.mark.parametrize(
    "start_time,end_time,sensor_id,expected",
    [
        (
            Time("2026-01-01T00:00:00", format="isot", scale="utc"),
            Time("2026-01-01T12:00:00", format="isot", scale="utc"),
            "REACH-1",
            [
                "2026-01-01T00:00:00.000Z..2026-01-01T06:00:00.000Z",
                "2026-01-01T06:00:01.000Z..2026-01-01T12:00:00.000Z",
            ],
        ),
        (
            Time("2026-01-01T00:00:00", format="isot", scale="utc"),
            Time("2026-01-01T00:20:00", format="isot", scale="utc"),
            "SENSOR-1",
            [
                "2026-01-01T00:00:00.000Z..2026-01-01T00:10:00.000Z",
                "2026-01-01T00:10:01.000Z..2026-01-01T00:20:00.000Z",
            ],
        ),
    ],
)
def test_get_reach_datetimelist(start_time, end_time, sensor_id, expected):
    assert udl.get_reach_datetimelist(start_time, end_time, sensor_id) == expected


@pytest.mark.parametrize(
    "dtlist,sensor_id,descriptor,expected",
    [
        (
            ["2026-01-01T00:00:00.000Z..2026-01-01T00:10:00.000Z"],
            "ALL",
            "electron",
            {
                "2026-01-01T00:00:00.000Z..2026-01-01T00:10:00.000Z": (
                    "https://unifieddatalibrary.com/udl/spaceenvobservation"
                    "?obTime=2026-01-01T00:00:00.000Z..2026-01-01T00:10:00.000Z"
                    "&source=Aerospace&dataMode=REAL&descriptor=electron&sort=obTime"
                )
            },
        ),
        (
            ["2026-01-01T00:00:00.000Z..2026-01-01T06:00:00.000Z"],
            "REACH-1",
            "proton",
            {
                "2026-01-01T00:00:00.000Z..2026-01-01T06:00:00.000Z": (
                    "https://unifieddatalibrary.com/udl/spaceenvobservation"
                    "?obTime=2026-01-01T00:00:00.000Z..2026-01-01T06:00:00.000Z"
                    "&idSensor=REACH-1&source=Aerospace&dataMode=REAL"
                    "&descriptor=proton&sort=obTime"
                )
            },
        ),
    ],
)
def test_get_reach_urllist(dtlist, sensor_id, descriptor, expected):
    assert udl.get_reach_urllist(dtlist, sensor_id, descriptor) == expected


@pytest.mark.parametrize(
    "sensor_id,start_time,end_time,output_format,expected",
    [
        (
            "ALL",
            Time("2026-01-01T00:00:00", format="isot", scale="utc"),
            Time("2026-01-01T00:10:00", format="isot", scale="utc"),
            "json",
            "REACH-ALL_20260101T000000_20260101T001000.json",
        ),
        (
            "REACH-1",
            Time("2026-01-01T12:30:45", format="isot", scale="utc"),
            Time("2026-01-01T18:45:59", format="isot", scale="utc"),
            "csv",
            "REACH-1_20260101T123045_20260101T184559.csv",
        ),
    ],
)
def test_build_reach_output_filename(
    sensor_id, start_time, end_time, output_format, expected
):
    assert (
        udl.build_reach_output_filename(sensor_id, start_time, end_time, output_format)
        == expected
    )


def test_write_reach_output_json_uses_tempfile_directory():
    obs = [
        {"idSensor": "REACH-1", "obTime": "2026-01-01T00:00:00.000Z", "flux": 12.5},
        {"idSensor": "REACH-1", "obTime": "2026-01-01T00:01:00.000Z", "flux": 13.0},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "reach_output.json"

        udl.write_reach_output(output_path, obs, "json")

        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8") as infile:
            saved = json.load(infile)

        assert saved == obs


def test_write_reach_output_csv_uses_tempfile_directory():
    obs = [
        {"idSensor": "REACH-1", "obTime": "2026-01-01T00:00:00.000Z", "flux": 12.5},
        {"idSensor": "REACH-1", "obTime": "2026-01-01T00:01:00.000Z", "flux": 13.0},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "reach_output.csv"

        udl.write_reach_output(output_path, obs, "csv")

        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8", newline="") as infile:
            rows = list(csv.DictReader(infile))

        assert rows == [
            {
                "idSensor": "REACH-1",
                "obTime": "2026-01-01T00:00:00.000Z",
                "flux": "12.5",
            },
            {
                "idSensor": "REACH-1",
                "obTime": "2026-01-01T00:01:00.000Z",
                "flux": "13.0",
            },
        ]


def test_write_reach_output_empty_csv_writes_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "reach_output.csv"

        udl.write_reach_output(output_path, [], "csv")

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == ""


def test_download_udl_reach_to_file_json_with_monkeypatched_udl(monkeypatch):
    fixed_now = Time("2026-01-01T00:30:00", format="isot", scale="utc")
    monkeypatch.setattr(udl.Time, "now", staticmethod(lambda: fixed_now))

    monkeypatch.setattr(
        udl,
        "get_reach_datetimelist",
        lambda start_time, end_time, sensor_id: ["window-1", "window-2"],
    )
    monkeypatch.setattr(
        udl,
        "get_reach_urllist",
        lambda dtlist, sensor_id, descriptor: {
            "window-1": "https://example.test/chunk1",
            "window-2": "https://example.test/chunk2",
        },
    )

    calls = []

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, headers, timeout):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        if url.endswith("chunk1"):
            return FakeResponse(
                [
                    {
                        "idSensor": "REACH-1",
                        "obTime": "2026-01-01T00:00:00.000Z",
                        "flux": 12.5,
                    }
                ]
            )
        return FakeResponse(
            {
                "idSensor": "REACH-1",
                "obTime": "2026-01-01T00:01:00.000Z",
                "flux": 13.0,
            }
        )

    monkeypatch.setattr(udl.requests, "get", fake_get)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = udl.download_UDL_reach_to_file(
            auth_token="Bearer test-token",
            sensor_id="REACH-1",
            descriptor="electron",
            output_format="json",
            delay_seconds=300,
            window_seconds=1500,
            output_dir=tmpdir,
        )

        assert output_path.parent == Path(tmpdir)
        assert output_path.exists()
        assert output_path.name == "REACH-1_20260101T000000_20260101T002500.json"

        with open(output_path, "r", encoding="utf-8") as infile:
            payload = json.load(infile)

        assert payload == [
            {
                "idSensor": "REACH-1",
                "obTime": "2026-01-01T00:00:00.000Z",
                "flux": 12.5,
            },
            {
                "idSensor": "REACH-1",
                "obTime": "2026-01-01T00:01:00.000Z",
                "flux": 13.0,
            },
        ]

    assert len(calls) == 2
    assert calls[0]["headers"] == {"Authorization": "Bearer test-token"}
    assert calls[0]["timeout"] == 120


def test_download_udl_reach_to_file_csv_with_monkeypatched_udl(monkeypatch):
    fixed_now = Time("2026-01-01T00:10:00", format="isot", scale="utc")
    monkeypatch.setattr(udl.Time, "now", staticmethod(lambda: fixed_now))

    monkeypatch.setattr(
        udl,
        "get_reach_datetimelist",
        lambda start_time, end_time, sensor_id: ["window-1"],
    )
    monkeypatch.setattr(
        udl,
        "get_reach_urllist",
        lambda dtlist, sensor_id, descriptor: {
            "window-1": "https://example.test/chunk1"
        },
    )

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "idSensor": "REACH-1",
                    "obTime": "2026-01-01T00:00:00.000Z",
                    "flux": 12.5,
                }
            ]

    monkeypatch.setattr(
        udl.requests, "get", lambda url, headers, timeout: FakeResponse()
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = udl.download_UDL_reach_to_file(
            auth_token="Bearer test-token",
            sensor_id="REACH-1",
            descriptor="proton",
            output_format="csv",
            delay_seconds=60,
            window_seconds=600,
            output_dir=Path(tmpdir),
        )

        assert output_path.parent == Path(tmpdir)
        assert output_path.exists()
        expected_end = fixed_now - udl.TimeDelta(60, format="sec")
        expected_start = expected_end - udl.TimeDelta(600, format="sec")
        expected_name = udl.build_reach_output_filename(
            "REACH-1", expected_start, expected_end, "csv"
        )
        assert output_path.name == expected_name

        with open(output_path, "r", encoding="utf-8", newline="") as infile:
            rows = list(csv.DictReader(infile))

        assert rows == [
            {
                "idSensor": "REACH-1",
                "obTime": "2026-01-01T00:00:00.000Z",
                "flux": "12.5",
            }
        ]


def test_download_udl_reach_to_file_rejects_invalid_output_format(monkeypatch):
    monkeypatch.setattr(
        udl.requests,
        "get",
        lambda *args, **kwargs: pytest.fail("requests.get should not be called"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="REACH_FILE_FORMAT"):
            udl.download_UDL_reach_to_file(
                auth_token="Bearer test-token",
                sensor_id="REACH-1",
                descriptor="electron",
                output_format="txt",
                delay_seconds=60,
                window_seconds=600,
                output_dir=tmpdir,
            )


# --- AdaptiveRateController tests ---


class TestAdaptiveRateController:
    def test_initial_rate(self):
        rc = AdaptiveRateController(initial_rate=10.0)
        assert rc.rate == 10.0

    def test_record_success_increases_rate(self):
        rc = AdaptiveRateController(
            initial_rate=5.0, additive_increase=1.0, max_rate=25.0
        )
        rc.record_success()
        assert rc.rate == 6.0
        rc.record_success()
        assert rc.rate == 7.0

    def test_record_rate_limit_decreases_rate(self):
        rc = AdaptiveRateController(
            initial_rate=10.0, multiplicative_decrease=0.5, min_rate=5.0
        )
        rc.record_rate_limit()
        assert rc.rate == 5.0

    def test_rate_does_not_exceed_max(self):
        rc = AdaptiveRateController(
            initial_rate=24.0, additive_increase=1.0, max_rate=25.0
        )
        rc.record_success()
        assert rc.rate == 25.0
        rc.record_success()
        assert rc.rate == 25.0

    def test_rate_does_not_go_below_min(self):
        rc = AdaptiveRateController(
            initial_rate=6.0, multiplicative_decrease=0.5, min_rate=5.0
        )
        rc.record_rate_limit()
        # 6.0 * 0.5 = 3.0, but clamped to min 5.0
        assert rc.rate == 5.0
        rc.record_rate_limit()
        # 5.0 * 0.5 = 2.5, clamped to 5.0
        assert rc.rate == 5.0

    def test_thread_safety(self):
        rc = AdaptiveRateController(
            initial_rate=10.0, additive_increase=0.1, max_rate=100.0, min_rate=1.0
        )
        errors = []

        def call_success():
            try:
                for _ in range(100):
                    rc.record_success()
            except Exception as e:
                errors.append(e)

        def call_rate_limit():
            try:
                for _ in range(50):
                    rc.record_rate_limit()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=call_success),
            threading.Thread(target=call_success),
            threading.Thread(target=call_rate_limit),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert rc.min_rate <= rc.rate <= rc.max_rate


# --- fetch_reach_chunk retry tests ---


def _make_fake_response(status_code, payload=None):
    """Build a fake requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload if payload is not None else []
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_fetch_reach_chunk_retries_on_429_then_succeeds(monkeypatch):
    """429 → 429 → 200 should succeed after 2 retries."""
    responses = [
        _make_fake_response(429),
        _make_fake_response(429),
        _make_fake_response(200, [{"flux": 1.0}]),
    ]
    call_count = {"n": 0}

    def fake_get(url, headers, timeout):
        idx = call_count["n"]
        call_count["n"] += 1
        return responses[idx]

    monkeypatch.setattr(udl.requests, "get", fake_get)
    monkeypatch.setattr(udl.time, "sleep", lambda s: None)  # skip actual sleeps

    rc = AdaptiveRateController(initial_rate=10.0, min_rate=1.0)

    dt, records = udl.fetch_reach_chunk(
        "window-1",
        "https://example.test/chunk1",
        "Bearer token",
        rate_controller=rc,
        max_retries=5,
    )

    assert dt == "window-1"
    assert records == [{"flux": 1.0}]
    assert call_count["n"] == 3
    # Rate should have decreased twice then increased once
    assert rc.rate < 10.0


def test_fetch_reach_chunk_raises_after_max_retries(monkeypatch):
    """Persistent 429s should raise after max_retries."""
    responses = [_make_fake_response(429) for _ in range(6)]
    call_count = {"n": 0}

    def fake_get(url, headers, timeout):
        idx = call_count["n"]
        call_count["n"] += 1
        return responses[idx]

    monkeypatch.setattr(udl.requests, "get", fake_get)
    monkeypatch.setattr(udl.time, "sleep", lambda s: None)

    rc = AdaptiveRateController(initial_rate=10.0, min_rate=1.0)

    with pytest.raises(Exception, match="HTTP 429"):
        udl.fetch_reach_chunk(
            "window-1",
            "https://example.test/chunk1",
            "Bearer token",
            rate_controller=rc,
            max_retries=5,
        )

    # 1 initial + 5 retries = 6 calls
    assert call_count["n"] == 6


def test_fetch_reach_chunk_works_without_rate_controller(monkeypatch):
    """When rate_controller is None, fetch should work as before."""
    resp = _make_fake_response(200, [{"flux": 2.5}])
    monkeypatch.setattr(udl.requests, "get", lambda url, headers, timeout: resp)

    dt, records = udl.fetch_reach_chunk(
        "window-1",
        "https://example.test/chunk1",
        "Bearer token",
        rate_controller=None,
    )

    assert dt == "window-1"
    assert records == [{"flux": 2.5}]


# --- Integration test: download with intermittent 429s ---


def test_download_udl_reach_to_file_with_intermittent_429s(monkeypatch):
    """Verify that download recovers from 429s and collects all chunks in order."""
    fixed_now = Time("2026-01-01T00:30:00", format="isot", scale="utc")
    monkeypatch.setattr(udl.Time, "now", staticmethod(lambda: fixed_now))

    monkeypatch.setattr(
        udl,
        "get_reach_datetimelist",
        lambda start_time, end_time, sensor_id: ["window-1", "window-2"],
    )
    monkeypatch.setattr(
        udl,
        "get_reach_urllist",
        lambda dtlist, sensor_id, descriptor: {
            "window-1": "https://example.test/chunk1",
            "window-2": "https://example.test/chunk2",
        },
    )

    # chunk1 returns 429 once then succeeds; chunk2 succeeds immediately
    chunk1_calls = {"n": 0}

    def fake_get(url, headers, timeout):
        if "chunk1" in url:
            chunk1_calls["n"] += 1
            if chunk1_calls["n"] == 1:
                return _make_fake_response(429)
            return _make_fake_response(
                200, [{"idSensor": "R1", "obTime": "t1", "flux": 1.0}]
            )
        return _make_fake_response(
            200, [{"idSensor": "R1", "obTime": "t2", "flux": 2.0}]
        )

    monkeypatch.setattr(udl.requests, "get", fake_get)
    monkeypatch.setattr(udl.time, "sleep", lambda s: None)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = udl.download_UDL_reach_to_file(
            auth_token="Bearer test-token",
            sensor_id="REACH-1",
            descriptor="electron",
            output_format="json",
            delay_seconds=300,
            window_seconds=1500,
            output_dir=tmpdir,
        )

        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        # Both chunks should be present, in order
        assert len(payload) == 2
        assert payload[0]["flux"] == 1.0
        assert payload[1]["flux"] == 2.0


def test_download_udl_reach_to_file_raises_on_empty_results(monkeypatch):
    """Verify that an empty combined result raises ValueError."""
    fixed_now = Time("2026-01-01T00:30:00", format="isot", scale="utc")
    monkeypatch.setattr(udl.Time, "now", staticmethod(lambda: fixed_now))

    monkeypatch.setattr(
        udl,
        "get_reach_datetimelist",
        lambda start_time, end_time, sensor_id: ["window-1"],
    )
    monkeypatch.setattr(
        udl,
        "get_reach_urllist",
        lambda dtlist, sensor_id, descriptor: {
            "window-1": "https://example.test/chunk1",
        },
    )

    monkeypatch.setattr(
        udl.requests,
        "get",
        lambda url, headers, timeout: _make_fake_response(200, []),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="No records returned"):
            udl.download_UDL_reach_to_file(
                auth_token="Bearer test-token",
                sensor_id="ALL",
                descriptor="electron",
                output_format="json",
                delay_seconds=300,
                window_seconds=1500,
                output_dir=tmpdir,
            )
