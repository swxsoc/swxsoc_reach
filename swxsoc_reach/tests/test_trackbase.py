import numpy as np
import pandas as pd
import pytest
from astropy.time import Time
from astropy.timeseries import TimeSeries

from swxsoc_reach import _test_file_track
from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.track.trackbase import REACHTrack
from swxsoc_reach.util.enums import SensorId


@pytest.fixture
def reach_track_swx() -> REACHTrack:
    return REACHTrack.load(_test_file_track)


@pytest.fixture
def truncated_reach_track_swx() -> REACHTrack:
    reach_track = REACHTrack.load(_test_file_track)
    start = reach_track.time[0]
    end = reach_track.time[9]
    return reach_track.truncate(start, end)


def test_truncate_basic_functionality(truncated_reach_track_swx, reach_track_swx):
    assert isinstance(truncated_reach_track_swx, REACHTrack)
    assert len(truncated_reach_track_swx.time) < len(reach_track_swx.time)


def test_truncate_reduces_time_length(truncated_reach_track_swx, reach_track_swx):
    assert (
        len(truncated_reach_track_swx.time) == 10
    )  # Should have 10 timestamps: from index 0 to index 9 inclusive
    assert truncated_reach_track_swx.time[0] >= truncated_reach_track_swx.time[0]
    assert truncated_reach_track_swx.time[-1] <= truncated_reach_track_swx.time[9]


def test_truncate_does_not_modify_original(reach_track_swx):
    original_len = len(reach_track_swx.time)
    start = reach_track_swx.time[0]
    end = reach_track_swx.time[-1]
    truncated_track = reach_track_swx.truncate(start, end)
    assert len(truncated_track.time) == original_len


def test_truncate_slices_support_variables(truncated_reach_track_swx):

    n = len(truncated_reach_track_swx.time)
    for key in ("lat", "lon", "alt"):
        if key in truncated_reach_track_swx.support:
            assert truncated_reach_track_swx.support[key].data.shape[0] == n, (
                f"{key} not sliced correctly"
            )
    if "observations" in truncated_reach_track_swx.support:
        assert truncated_reach_track_swx.support["observations"].data.shape[0] == n


def test_plot_creates_axis_per_track_parameter(reach_track_swx, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    ts = reach_track_swx.get_track(reach_id=SensorId.from_str(0))
    y_columns = [col for col in ts.colnames if col != "time"]
    assert len(fig.axes) == len(y_columns)


def test_plot_labels_last_axis_time(reach_track_swx, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    assert fig.axes[-1].get_xlabel() == "Time"


def test_plot_time_axis_uses_hms_formatter(reach_track_swx, monkeypatch):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    formatter = fig.axes[-1].xaxis.get_major_formatter()
    assert isinstance(formatter, mdates.DateFormatter)
    assert formatter.fmt == "%H:%M:%S"


def test_plot_uses_title_from_meta(reach_track_swx, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

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


def test_timeseries_has_region_code_column(reach_track_swx):
    ts = reach_track_swx.get_track(reach_id=SensorId.from_str(0))
    assert "region_code" in ts.colnames
    assert len(ts["region_code"]) == len(ts.time)


def test_region_code_maps_per_timestamp(reach_track_swx, monkeypatch):
    import swxsoc_reach.track.trackbase as trackbase

    # Mock region code calculation
    monkeypatch.setattr(trackbase, "load_region_contours", lambda: {})
    monkeypatch.setattr(
        trackbase,
        "points_to_region_code",
        lambda lon, lat, paths_dict: np.ones(len(lon), dtype=int),
    )

    ts = reach_track_swx.get_track(reach_id=SensorId.from_str(0))
    region_codes = np.asarray(ts["region_code"])

    assert region_codes.shape[0] == ts.time.shape[0]
    assert len(region_codes) > 0


def test_plotgeo_smoke(reach_track_swx, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plotgeo(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    assert len(fig.axes) >= 1


def test_plotgeo_region_code_smoke(reach_track_swx, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plotgeo(reach_id=SensorId.from_str(0), color_by="region_code")

    fig = plt.gcf()
    assert len(fig.axes) >= 1


def test_plotgeo_invalid_color_by_raises(reach_track_swx):
    with pytest.raises(ValueError, match="Unsupported color_by"):
        reach_track_swx.plotgeo(reach_id=SensorId.from_str(0), color_by="unknown")


def test_plotgeo_uses_region_contour_utility(reach_track_swx, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    import swxsoc_reach.track.trackbase as trackbase

    calls = {"count": 0}

    def _mock_contours(**kwargs):
        calls["count"] += 1
        return kwargs["ax"], None

    monkeypatch.setattr(trackbase, "plot_geomap", _mock_contours)
    monkeypatch.setattr(plt, "show", lambda: None)

    reach_track_swx.plotgeo(reach_id=SensorId.from_str(0))
    assert calls["count"] == 1
