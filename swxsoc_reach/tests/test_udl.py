import csv
import json
import tempfile
from pathlib import Path

import pytest
from astropy.time import Time

import swxsoc_reach.net.udl as udl


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
    assert calls[0]["timeout"] == 60


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
