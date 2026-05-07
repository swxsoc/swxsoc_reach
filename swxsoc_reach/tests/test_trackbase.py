import numpy as np
import pandas as pd
import pytest
from astropy.time import Time
from astropy.timeseries import TimeSeries

from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.track.trackbase import REACHTrack
from swxsoc_reach.util.enums import SensorId


def _make_reach_track(n_time: int = 6) -> REACHTrack:
    """Build a minimal REACHTrack with ``n_time`` time steps and one sensor."""
    rows = []
    for i in range(n_time):
        # Add DOSE0 record
        rows.append(
            {
                "createdAt": f"2026-01-01T00:00:0{i}Z",
                "idSensor": "REACH-001",
                "obDescription": "DOSE0 (Flavor U) in rad/second",
                "obTime": f"2026-01-01T00:00:0{i}Z",
                "obValue": float(i + 1),
                "observatoryName": "REACH",
                "lat": 10.0 + i,
                "lon": 20.0 + i,
                "alt": 500.0,
                "obQuality": 1,
                "senPos0": 1000.0,
                "senPos1": 2000.0,
                "senPos2": 3000.0,
                "descriptor": "QUICKLOOK",
            }
        )
        # Add DOSE1 record
        rows.append(
            {
                "createdAt": f"2026-01-01T00:00:0{i}Z",
                "idSensor": "REACH-001",
                "obDescription": "DOSE1 (Flavor V) in rad/second",
                "obTime": f"2026-01-01T00:00:0{i}Z",
                "obValue": float(i + 0.5),
                "observatoryName": "REACH",
                "lat": 10.0 + i,
                "lon": 20.0 + i,
                "alt": 500.0,
                "obQuality": 1,
                "senPos0": 1000.0,
                "senPos1": 2000.0,
                "senPos2": 3000.0,
                "descriptor": "QUICKLOOK",
            }
        )
    df = pd.DataFrame(rows)
    swx = build_swxdata(df)
    return REACHTrack(
        timeseries=swx.timeseries,
        support=swx.support,
        meta=swx.meta,
        schema=swx.schema,
    )


@pytest.fixture
def reach_track_swx() -> REACHTrack:
    return _make_reach_track(n_time=6)


def test_truncate_reduces_time_length(reach_track_swx):
    start = Time("2026-01-01T00:00:01")
    end = Time("2026-01-01T00:00:03")
    truncated = reach_track_swx.truncate(start, end)
    assert len(truncated.time) == 3


def test_truncate_time_bounds_are_correct(reach_track_swx):
    start = Time("2026-01-01T00:00:02")
    end = Time("2026-01-01T00:00:04")
    truncated = reach_track_swx.truncate(start, end)
    assert truncated.time[0] >= start
    assert truncated.time[-1] <= end


def test_truncate_does_not_modify_original(reach_track_swx):
    original_len = len(reach_track_swx.time)
    start = Time("2026-01-01T00:00:01")
    end = Time("2026-01-01T00:00:03")
    reach_track_swx.truncate(start, end)
    assert len(reach_track_swx.time) == original_len


def test_truncate_slices_support_variables(reach_track_swx):
    start = Time("2026-01-01T00:00:02")
    end = Time("2026-01-01T00:00:04")
    truncated = reach_track_swx.truncate(start, end)
    n = len(truncated.time)
    for key in ("lat", "lon", "alt"):
        if key in truncated.support:
            assert truncated.support[key].data.shape[0] == n, (
                f"{key} not sliced correctly"
            )
    if "observations" in truncated.support:
        assert truncated.support["observations"].data.shape[0] == n


def test_get_track_on_truncated_track_has_consistent_length(reach_track_swx):
    """Regression: get_track on a truncated REACHTrack must not raise an array size error."""
    start = Time("2026-01-01T00:00:01")
    end = Time("2026-01-01T00:00:03")
    truncated = reach_track_swx.truncate(start, end)
    # reach_id=0 maps to REACH-101 (the first sensor, index 0)
    ts = truncated.get_track(reach_id=SensorId.from_str(0))
    assert len(ts) == len(truncated.time)


@pytest.fixture
def reach_track(reach_track_swx):
    """Use the same fixture as reach_track_swx for consistency."""
    return reach_track_swx


def test_plot_creates_axis_per_track_parameter(reach_track, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    ts = reach_track.get_track(reach_id=SensorId.from_str(0))
    y_columns = [col for col in ts.colnames if col != "time"]
    assert len(fig.axes) == len(y_columns)


def test_plot_labels_last_axis_time(reach_track, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    assert fig.axes[-1].get_xlabel() == "Time"


def test_plot_time_axis_uses_hms_formatter(reach_track, monkeypatch):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    formatter = fig.axes[-1].xaxis.get_major_formatter()
    assert isinstance(formatter, mdates.DateFormatter)
    assert formatter.fmt == "%H:%M:%S"


def test_plot_uses_title_from_meta(reach_track, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    # Title should contain the reach_id string
    assert fig.axes[0].get_title() != ""


def test_plot_raises_when_no_parameters(monkeypatch):
    import matplotlib.pyplot as plt

    # Create an empty track with no track data
    ts = TimeSeries(time=["2026-01-01T00:00:00", "2026-01-01T00:01:00"])
    ts.time.meta = {"CATDESC": "Observation Time", "VAR_TYPE": "support_data"}
    from swxsoc_reach.util.schema import REACHDataSchema

    schema = REACHDataSchema()
    meta = dict(schema.default_global_attributes)
    meta["Data_level"] = "L2"
    meta["Data_version"] = "1.0.0"
    meta["Descriptor"] = "test"

    track = REACHTrack(timeseries=ts, support={}, meta=meta, schema=schema)

    monkeypatch.setattr(plt, "show", lambda: None)
    with pytest.raises(Exception):  # Could be KeyError or other errors
        track.plot(reach_id=SensorId.from_str(0))


def test_timeseries_has_region_code_column(reach_track):
    ts = reach_track.get_track(reach_id=SensorId.from_str(0))
    assert "region_code" in ts.colnames
    assert len(ts["region_code"]) == len(ts.time)


def test_region_code_maps_per_timestamp(reach_track, monkeypatch):
    import swxsoc_reach.track.trackbase as trackbase

    # Mock region code calculation
    monkeypatch.setattr(trackbase, "load_region_contours", lambda: {})
    monkeypatch.setattr(
        trackbase,
        "points_to_region_code",
        lambda lon, lat, paths_dict: np.ones(len(lon), dtype=int),
    )

    ts = reach_track.get_track(reach_id=SensorId.from_str(0))
    region_codes = np.asarray(ts["region_code"])

    assert region_codes.shape[0] == ts.time.shape[0]
    assert len(region_codes) > 0


def test_plotgeo_smoke(reach_track, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plotgeo(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    assert len(fig.axes) >= 1


def test_plotgeo_region_code_smoke(reach_track, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plotgeo(reach_id=SensorId.from_str(0), color_by="region_code")

    fig = plt.gcf()
    assert len(fig.axes) >= 1


def test_plotgeo_invalid_color_by_raises(reach_track):
    with pytest.raises(ValueError, match="Unsupported color_by"):
        reach_track.plotgeo(reach_id=SensorId.from_str(0), color_by="unknown")


def test_plotgeo_uses_region_contour_utility(reach_track, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    import swxsoc_reach.track.trackbase as trackbase

    calls = {"count": 0}

    def _mock_contours(**kwargs):
        calls["count"] += 1
        return kwargs["ax"], None

    monkeypatch.setattr(
        trackbase, "plot_region_code_contours_on_geomap", _mock_contours
    )
    monkeypatch.setattr(plt, "show", lambda: None)

    reach_track.plotgeo(reach_id=SensorId.from_str(0))
    assert calls["count"] == 1
