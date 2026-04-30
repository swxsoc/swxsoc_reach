import numpy as np
import pytest
from astropy.timeseries import TimeSeries

from swxsoc_reach.track.trackbase import REACHTrack


class _FakeVar:
    def __init__(self, data, unit=None):
        self.data = data
        self.unit = unit


class _FakeTrackData:
    def __init__(self):
        n_time = 6
        self.meta = {"title": "Test REACH Track"}
        self._vars = {
            "time": _FakeVar(
                np.array([f"2026-01-01T00:00:0{i}" for i in range(n_time)])
            ),
            "observations": _FakeVar(
                np.arange(n_time * 2 * 2, dtype=float).reshape(n_time, 2, 2),
                unit="rad/s",
            ),
            "lon": _FakeVar(np.linspace(-100, -90, n_time * 2).reshape(n_time, 2)),
            "lat": _FakeVar(np.linspace(10, 20, n_time * 2).reshape(n_time, 2)),
            "alt": _FakeVar(np.linspace(500, 550, n_time * 2).reshape(n_time, 2)),
            "observation_flavors": _FakeVar(
                np.array(
                    [
                        ["DOSE0 (Flavor U)", "DOSE1 (Flavor V)"],
                        ["DOSE0 (Flavor W)", "DOSE1 (Flavor X)"],
                    ],
                    dtype=object,
                )
            ),
            "sensor_ids": _FakeVar(np.array(["REACH-A", "REACH-B"], dtype=object)),
        }

    def __getitem__(self, key):
        if key == "time":
            return self._vars[key].data
        return self._vars[key]


@pytest.fixture
def reach_track():
    return REACHTrack(trackdata=_FakeTrackData(), reach_id=0, dose_id=1)


def test_plot_creates_axis_per_track_parameter(reach_track, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot()

    fig = plt.gcf()
    y_columns = [col for col in reach_track.data.colnames if col != "time"]
    assert len(fig.axes) == len(y_columns)


def test_plot_labels_last_axis_time(reach_track, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot()

    fig = plt.gcf()
    assert fig.axes[-1].get_xlabel() == "Time"


def test_plot_time_axis_uses_hms_formatter(reach_track, monkeypatch):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot()

    fig = plt.gcf()
    formatter = fig.axes[-1].xaxis.get_major_formatter()
    assert isinstance(formatter, mdates.DateFormatter)
    assert formatter.fmt == "%H:%M:%S"


def test_plot_uses_title_from_meta(reach_track, monkeypatch):
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plot()

    fig = plt.gcf()
    assert fig.axes[0].get_title() == "Test REACH Track"


def test_plot_raises_when_no_parameters(monkeypatch):
    import matplotlib.pyplot as plt

    track = REACHTrack(trackdata=_FakeTrackData(), reach_id=0, dose_id=0)
    track._data = TimeSeries(time=track._data.time)

    monkeypatch.setattr(plt, "show", lambda: None)
    with pytest.raises(ValueError, match="No track parameters available"):
        track.plot()


def test_timeseries_has_region_code_column(reach_track):
    assert "region_code" in reach_track.data.colnames
    assert len(reach_track.data["region_code"]) == len(reach_track.data.time)


def test_region_code_maps_per_timestamp(monkeypatch):
    import swxsoc_reach.track.trackbase as trackbase

    # Build a tiny 2x2 deterministic lookup grid.
    fake_lon = np.array([-100.0, -90.0, -100.0, -90.0])
    fake_lat = np.array([10.0, 10.0, 20.0, 20.0])
    fake_codes = np.array([1, 2, 3, 4])
    monkeypatch.setattr(
        trackbase, "compute_region_code", lambda lon, lat: np.array([1, 2, 3, 4, 1, 2])
    )

    track = REACHTrack(trackdata=_FakeTrackData(), reach_id=0, dose_id=0)
    region_codes = np.asarray(track.data["region_code"])

    assert region_codes.shape[0] == track.data.time.shape[0]
    assert set(np.unique(region_codes)).issubset({1, 2, 3, 4})


def test_plotgeo_smoke(reach_track, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plotgeo()

    fig = plt.gcf()
    assert len(fig.axes) >= 1
    assert fig.axes[0].get_title() == "Test REACH Track"


def test_plotgeo_region_code_smoke(reach_track, monkeypatch):
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track.plotgeo(color_by="region_code")

    fig = plt.gcf()
    assert len(fig.axes) >= 1


def test_plotgeo_invalid_color_by_raises(reach_track):
    with pytest.raises(ValueError, match="Unsupported color_by"):
        reach_track.plotgeo(color_by="unknown")


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

    reach_track.plotgeo()
    assert calls["count"] == 1


def test_subtrack_returns_smaller_interval(reach_track):
    sub = reach_track.subtrack("2026-01-01T00:00:01", "2026-01-01T00:00:03")
    assert len(sub.data.time) == 3
    assert sub.data.time[0].isot.startswith("2026-01-01T00:00:01")
    assert sub.data.time[-1].isot.startswith("2026-01-01T00:00:03")


def test_subtrack_supports_open_ended_interval(reach_track):
    sub = reach_track.subtrack(start="2026-01-01T00:00:04")
    assert len(sub.data.time) == 2
    assert sub.data.time[0].isot.startswith("2026-01-01T00:00:04")


def test_subtrack_raises_for_empty_interval(reach_track):
    with pytest.raises(ValueError, match="No track samples found"):
        reach_track.subtrack("2026-01-01T01:00:00", "2026-01-01T02:00:00")


def test_subtrack_raises_for_invalid_bounds(reach_track):
    with pytest.raises(ValueError, match="end must be greater"):
        reach_track.subtrack("2026-01-01T00:00:05", "2026-01-01T00:00:01")


def test_slice_calls_subtrack(reach_track):
    sliced = reach_track["2026-01-01T00:00:01":"2026-01-01T00:00:03"]
    sub = reach_track.subtrack("2026-01-01T00:00:01", "2026-01-01T00:00:03")

    assert len(sliced.data.time) == len(sub.data.time)
    assert sliced.data.time[0].isot == sub.data.time[0].isot
    assert sliced.data.time[-1].isot == sub.data.time[-1].isot


def test_slice_with_invalid_step_raises(reach_track):
    with pytest.raises(ValueError, match="Slice step is not supported"):
        _ = reach_track["2026-01-01T00:00:00":"2026-01-01T00:00:05":2]


def test_non_slice_getitem_raises(reach_track):
    with pytest.raises(TypeError, match="only supports slicing"):
        _ = reach_track[0]
