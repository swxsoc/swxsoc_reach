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
