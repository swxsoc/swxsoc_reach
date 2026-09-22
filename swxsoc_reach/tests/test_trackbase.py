from unittest.mock import Mock

import astropy.units as u
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pytest
from astropy.timeseries import TimeSeries
from cartopy.mpl.geoaxes import GeoAxes

from swxsoc_reach import _test_file_track, log
from swxsoc_reach.geomap import GenericGeoMap
from swxsoc_reach.track.trackbase import REACHTrack
from swxsoc_reach.util.enums import Flavor, SensorId


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
    assert (
        len(truncated_reach_track_swx.time) == 10
    )  # Should have 10 timestamps: from index 0 to index 9 inclusive
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


def test_to_tracks_filters_all_sensors_by_flavor(reach_track_swx):
    tracks = reach_track_swx.to_tracks(Flavor.X)
    flavor_grid = np.vectorize(Flavor.from_str)(
        reach_track_swx["dosimeter_flavors"].data
    )
    sensor_indices, dosimeter_indices = np.nonzero(flavor_grid == Flavor.X)

    dose_rate = reach_track_swx["dose_rate"].data[:, sensor_indices, dosimeter_indices]
    longitude = reach_track_swx["lon"].data[:, sensor_indices]
    latitude = reach_track_swx["lat"].data[:, sensor_indices]
    altitude = reach_track_swx["alt"].data[:, sensor_indices]
    valid_measurements = (
        np.isfinite(dose_rate)
        & np.isfinite(longitude)
        & np.isfinite(latitude)
        & np.isfinite(altitude)
    )
    valid_measurements &= np.count_nonzero(valid_measurements, axis=0) >= 2
    expected_measurements = np.count_nonzero(valid_measurements)
    assert len(tracks.time) == expected_measurements
    assert tracks["dose_rate"].shape == (expected_measurements,)
    assert (
        tracks["sensor_id"].tolist()
        == np.tile(
            reach_track_swx["sensor_ids"].data[sensor_indices],
            len(reach_track_swx.time),
        )[valid_measurements.ravel()].tolist()
    )
    assert (
        tracks["flavor"].tolist()
        == np.tile(
            [
                selected_flavor.name
                for selected_flavor in flavor_grid[sensor_indices, dosimeter_indices]
            ],
            len(reach_track_swx.time),
        )[valid_measurements.ravel()].tolist()
    )
    assert "region_code" in tracks.colnames
    assert "direction" in tracks.colnames
    assert set(tracks["direction"]) <= {"north", "south"}
    assert set(tracks["direction"]) == {"north", "south"}


def test_to_region_indices_aggregates_each_region(reach_track_swx):
    tracks = reach_track_swx.to_tracks(Flavor.X)
    aggregated = reach_track_swx.to_region_indices(
        Flavor.X,
        integration_time=10 * u.s,
        statistic="count",
    )
    region_codes = np.asarray(tracks["region_code"], dtype=float)
    expected_codes = np.unique(region_codes[np.isfinite(region_codes)]).astype(int)

    assert aggregated.meta["statistic"] == "count"
    assert aggregated.meta["integration_time"] == "10.0 s"
    assert set(aggregated.colnames) == {
        "time",
        *[f"region_code_{code}" for code in expected_codes],
    }
    assert all(
        aggregated[f"region_code_{code}"].unit == u.count for code in expected_codes
    )
    dose_rates = tracks["dose_rate"].to_value(u.rad / u.s)
    for code in expected_codes:
        expected_count = np.count_nonzero(
            (region_codes == code) & np.isfinite(dose_rates)
        )
        assert aggregated[f"region_code_{code}"].sum().value == expected_count


def test_add_concatenates_tracks_without_modifying_inputs(
    truncated_reach_track_swx, monkeypatch
):
    original_len = len(truncated_reach_track_swx.time)
    warning = Mock()
    monkeypatch.setattr(log, "warning", warning)

    combined_track = truncated_reach_track_swx + truncated_reach_track_swx

    warning.assert_called_once_with("Discarded %d duplicate time-series row(s).", 10)
    assert isinstance(combined_track, REACHTrack)
    assert len(combined_track.time) == original_len
    assert len(truncated_reach_track_swx.time) == original_len
    for key, data in truncated_reach_track_swx.data["support"].items():
        combined_data = combined_track.data["support"][key].data
        if data.data.shape[0] == original_len:
            assert combined_data.shape[0] == original_len
        else:
            assert np.array_equal(
                combined_data,
                data.data,
                equal_nan=np.issubdtype(data.data.dtype, np.inexact),
            )


def test_add_reconstructs_track_from_two_halves(reach_track_swx):
    midpoint = len(reach_track_swx.time) // 2
    first_half = reach_track_swx.truncate(
        reach_track_swx.time[0], reach_track_swx.time[midpoint - 1]
    )
    second_half = reach_track_swx.truncate(
        reach_track_swx.time[midpoint], reach_track_swx.time[-1]
    )

    reconstructed_track = first_half + second_half

    assert np.all(reconstructed_track.time == reach_track_swx.time)
    for key, data in reach_track_swx.data["support"].items():
        reconstructed_data = reconstructed_track.data["support"][key].data
        assert np.array_equal(
            reconstructed_data,
            data.data,
            equal_nan=np.issubdtype(data.data.dtype, np.inexact),
        )


def test_add_preserves_deduplicated_spectra(reach_track_swx):
    combined_track = reach_track_swx + reach_track_swx

    assert set(combined_track.data["spectra"]) == set(reach_track_swx.data["spectra"])
    for key, data in reach_track_swx.data["spectra"].items():
        combined_data = combined_track.data["spectra"][key].data
        assert combined_data.shape == data.data.shape
        assert np.array_equal(
            combined_data,
            data.data,
            equal_nan=np.issubdtype(data.data.dtype, np.inexact),
        )


def test_truncate_slices_support_variables(truncated_reach_track_swx):
    n = len(truncated_reach_track_swx.time)
    for key in ("lat", "lon", "alt"):
        if key in truncated_reach_track_swx.support:
            assert truncated_reach_track_swx.support[key].data.shape[0] == n, (
                f"{key} not sliced correctly"
            )
    if "observations" in truncated_reach_track_swx.support:
        assert truncated_reach_track_swx.support["observations"].data.shape[0] == n


def test_truncate_no_overlap(reach_track_swx):
    start = reach_track_swx.time[-1] + 1
    end = reach_track_swx.time[-1] + 10
    with pytest.raises(ValueError):
        reach_track_swx.truncate(start, end)


def test_plot_creates_axis_per_track_parameter(reach_track_swx, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    ts = reach_track_swx.get_track(reach_id=SensorId.from_str(0))
    y_columns = [col for col in ts.colnames if col != "time"]
    assert len(fig.axes) == len(y_columns)


def test_plot_labels_last_axis_time(reach_track_swx, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    assert fig.axes[-1].get_xlabel() == "Time"


def test_plot_time_axis_uses_hms_formatter(reach_track_swx, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    formatter = fig.axes[-1].xaxis.get_major_formatter()
    assert isinstance(formatter, mdates.DateFormatter)
    assert formatter.fmt == "%H:%M:%S"


def test_plot_uses_title_from_meta(reach_track_swx, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plot(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    # Title should contain the reach_id string
    assert fig.axes[0].get_title() != ""


def test_plot_raises_when_no_parameters(monkeypatch):
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


def test_plotgeo_creates_geoaxes(reach_track_swx, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    reach_track_swx.plotgeo(reach_id=SensorId.from_str(0))

    fig = plt.gcf()
    assert len(fig.axes) >= 1
    # The map is drawn on a cartopy GeoAxes (PlateCarree projection).
    assert isinstance(fig.axes[0], GeoAxes)


def test_plotgeo_accepts_second_dosimeter(reach_track_swx, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    # dose_index=1 selects the second dosimeter and should not raise.
    reach_track_swx.plotgeo(reach_id=SensorId.from_str(0), dose_index=1)


def test_plotgeo_raises_for_invalid_dose_index(reach_track_swx, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    with pytest.raises(ValueError):
        reach_track_swx.plotgeo(reach_id=SensorId.from_str(0), dose_index=2)


def test_timeseries_has_region_code_column(reach_track_swx):
    ts = reach_track_swx.get_track(reach_id=SensorId.from_str(0))
    assert "region_code" in ts.colnames
    assert len(ts["region_code"]) == len(ts.time)


def test_get_track_filters_nonfinite_measurements(reach_track_swx):
    reach_index = SensorId.from_str(0).to_index()
    reach_track_swx["dose_rate"].data[0, reach_index, 0] = np.nan
    reach_track_swx["lat"].data[1, reach_index] = np.nan

    ts = reach_track_swx.get_track(reach_id=SensorId.from_str(0))

    assert len(ts) == len(reach_track_swx.time) - 2
    assert np.isfinite(ts["dose0"].value).all()
    assert np.isfinite(ts["dose1"].value).all()
    assert np.isfinite(ts["longitude"].value).all()
    assert np.isfinite(ts["latitude"].value).all()
    assert np.isfinite(ts["altitude"].value).all()


@pytest.fixture
def sparse_flavor_reach_track(reach_track_swx) -> REACHTrack:
    reach_track_swx["dosimeter_flavors"].data[:] = [
        "DOSE1 (Flavor V) in rad/second",
        "DOSE2 (Flavor Y) in rad/second",
    ]
    return reach_track_swx


def test_to_geomap_preserves_canonical_flavor_axis(sparse_flavor_reach_track):
    geomap = sparse_flavor_reach_track.to_geomap()

    assert isinstance(geomap, GenericGeoMap)
    assert list(geomap.flavor_names) == ["U", "V", "W", "X", "Y", "Z"]
    for statistic in ("sum", "mean", "median", "count", "min", "max", "std"):
        assert geomap[f"{statistic}_map"].data.shape[1] == 6


def test_to_geomap_fills_missing_flavors(sparse_flavor_reach_track):
    geomap = sparse_flavor_reach_track.to_geomap()

    for flavor in (Flavor.U, Flavor.W, Flavor.X, Flavor.Z):
        assert np.isnan(geomap.map_data("median", flavor)).all()
        assert np.array_equal(geomap.map_data("count", flavor), np.zeros(geomap.shape))

    assert np.isfinite(geomap.map_data("median", Flavor.V)).any()
    assert np.isfinite(geomap.map_data("median", Flavor.Y)).any()
