import matplotlib.pyplot as plt
import numpy as np
import pytest
from astropy import units as u
from astropy.nddata import NDData
from cartopy import crs as ccrs
from cartopy.mpl.geoaxes import GeoAxes
from matplotlib.collections import QuadMesh

from swxsoc_reach import _test_file_track
from swxsoc_reach.geomap import GenericGeoMap
from swxsoc_reach.track.trackbase import REACHTrack
from swxsoc_reach.util.enums import Flavor


@pytest.fixture(autouse=True)
def _close_figures():
    """Close any matplotlib figures created during a test to avoid leaks."""
    yield
    plt.close("all")


@pytest.fixture
def test_geomap():
    geomap = REACHTrack.load(_test_file_track).to_geomap()
    return geomap


@pytest.fixture
def test_geomap_coarse():
    geomap = REACHTrack.load(_test_file_track).to_geomap(
        lon_resolution=10.0 * u.deg, lat_resolution=10.0 * u.deg
    )
    return geomap


def test_geomap_loads(test_geomap):
    """Test that GenericGeoMap loads correctly from a REACHTrack."""
    assert isinstance(test_geomap, GenericGeoMap)
    assert test_geomap.flavor == Flavor.ALL
    assert test_geomap.map_data("median", Flavor.X).shape == (
        180,
        360,
    )  # (flavor, lat, lon)


def test_geomap_coarse_loads(test_geomap_coarse):
    """Test that GenericGeoMap loads correctly from a REACHTrack."""
    assert isinstance(test_geomap_coarse, GenericGeoMap)
    assert test_geomap_coarse.flavor == Flavor.ALL
    assert test_geomap_coarse.map_data("median", Flavor.X).shape == (
        18,
        36,
    )  # (flavor, lat, lon)


def test_shape_property(test_geomap):
    """shape property should return spatial shape (last 2 dims when time is present)."""
    # shape should return just the spatial dimensions, not including time axis
    assert test_geomap.shape == (180, 360)


def test_flavor_names_property(test_geomap):
    """flavor_names should list the six dosimeter flavors in canonical order."""
    assert list(test_geomap.flavor_names) == ["U", "V", "W", "X", "Y", "Z"]


def test_statistic_maps_preserve_six_flavor_axis(test_geomap):
    """All statistic maps should retain the canonical six-flavor axis."""
    for statistic in ("sum", "mean", "median", "count", "min", "max", "std"):
        assert test_geomap[f"{statistic}_map"].data.shape[1] == 6


def test_lon_property(test_geomap):
    """lon should return 1D longitude bin centers spanning the globe."""
    lon = test_geomap.lon
    assert lon.ndim == 1
    assert lon.shape == (360,)
    assert lon.min() == pytest.approx(-179.5)
    assert lon.max() == pytest.approx(179.5)


def test_lat_property(test_geomap):
    """lat should return 1D latitude bin centers spanning the globe."""
    lat = test_geomap.lat
    assert lat.ndim == 1
    assert lat.shape == (180,)
    assert lat.min() == pytest.approx(-89.5)
    assert lat.max() == pytest.approx(89.5)


def test_flavor_property(test_geomap):
    """flavor should return Flavor from metadata."""
    assert test_geomap.flavor == Flavor.ALL


def test_coordinate_system_property(test_geomap):
    """coordinate_system should return value from metadata."""
    assert test_geomap.coordinate_system == "geodetic"


def test_extent_property(test_geomap):
    """extent should return (lon_min, lon_max, lat_min, lat_max)."""
    lon_min, lon_max, lat_min, lat_max = test_geomap.extent
    assert lon_min == pytest.approx(-179.5)
    assert lon_max == pytest.approx(179.5)
    assert lat_min == pytest.approx(-89.5)
    assert lat_max == pytest.approx(89.5)


def test_lon_lat_grid_property(test_geomap):
    """lon_lat_grid should meshgrid 1D lon/lat arrays."""
    lon2d, lat2d = test_geomap.lon_lat_grid
    assert lon2d.shape == test_geomap.shape
    assert lat2d.shape == test_geomap.shape


def test_contains_true_for_existing_variables(test_geomap):
    """__contains__ should resolve names across timeseries, support, and spectra."""
    assert "dosimeter_flavor_names" in test_geomap
    assert "statistics" in test_geomap
    assert "lon" in test_geomap
    assert "lat" in test_geomap
    assert "median_map" in test_geomap
    assert "nonexistent_variable" not in test_geomap


def test_contains_does_not_raise_on_integer_like_key(test_geomap):
    """Regression: membership must not fall back to integer-index iteration.

    Before ``__contains__`` was defined, ``in`` fell back to ``self[0]``,
    ``self[1]``, ... which raised ``KeyError: 'Variable 0 not found'``. It must
    now return False cleanly instead.
    """
    assert "0" not in test_geomap
    assert "1" not in test_geomap


def test_map_data(test_geomap):
    """map_data should return the correct statistic map for a given flavor."""
    median_x = test_geomap.map_data("median", Flavor.X)
    assert median_x.shape == test_geomap.shape
    assert not np.isnan(median_x).all()  # Should have some valid data

    # Raise ValueError for invalid statistic
    with pytest.raises(ValueError):
        test_geomap.map_data("invalid_statistic", Flavor.X)

    # Raise ValueError for a flavor that is not gridded individually.
    # The per-flavor maps only contain U, V, W, X, Y, Z, so Flavor.ALL is absent.
    with pytest.raises(ValueError):
        test_geomap.map_data("median", Flavor.ALL)


def test_map_data_raises_for_misaligned_flavor_metadata(test_geomap):
    """map_data should fail loudly when flavor metadata and data axes disagree."""
    original = test_geomap["dosimeter_flavor_names"]
    test_geomap.support["dosimeter_flavor_names"] = NDData(
        data=original.data[:-1],
        meta=original.meta,
    )

    with pytest.raises(
        ValueError, match="flavor metadata does not match the data axis"
    ):
        test_geomap.map_data("median", Flavor.X)


def test_plot_returns_geoaxes_and_mesh(test_geomap):
    """plot should return a cartopy GeoAxes and a QuadMesh artist by default."""
    ax, mesh = test_geomap.plot(flavor=Flavor.X, statistic="median")
    assert isinstance(ax, GeoAxes)
    assert isinstance(mesh, QuadMesh)

    # Assert Title is Properly Formed
    title = ax.get_title()
    assert Flavor.X.label in title
    assert "median map" in title
    assert test_geomap.meta["Time_start"] in title


def test_plot_log_scale_adds_colorbar(test_geomap):
    """With the default log scale + colorbar, an extra colorbar axes is added."""
    ax, _ = test_geomap.plot(flavor=Flavor.X, log_scale=True, add_colorbar=True)
    # main map axes + horizontal colorbar axes
    assert len(ax.figure.axes) == 2


def test_plot_without_colorbar_has_single_axes(test_geomap):
    """When add_colorbar=False no colorbar axes should be created."""
    ax, _ = test_geomap.plot(flavor=Flavor.X, add_colorbar=False)
    assert len(ax.figure.axes) == 1


def test_plot_count_statistic_uses_linear_scale(test_geomap):
    """statistic='count' should plot on a linear scale regardless of log_scale."""
    ax, mesh = test_geomap.plot(flavor=Flavor.X, statistic="count", log_scale=True)
    # Linear count scale should not use the fixed log range of [-7, -2].
    assert mesh.norm.vmin != -7


def test_plot_linear_scale_non_count(test_geomap):
    """log_scale=False on a non-count statistic should autoscale linearly."""
    ax, mesh = test_geomap.plot(flavor=Flavor.X, statistic="median", log_scale=False)
    assert isinstance(mesh, QuadMesh)


def test_plot_uses_provided_axes(test_geomap):
    """When an axes is supplied, plot should draw into it and return it."""
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    result_ax, _ = test_geomap.plot(flavor=Flavor.X, ax=ax, add_colorbar=False)
    assert result_ax is ax


def test_plot_draw_contours_log_scale(test_geomap):
    """draw_contours=True on a log scale should add contour artists."""
    ax, _ = test_geomap.plot(flavor=Flavor.X, draw_contours=True, log_scale=True)
    assert len(ax.collections) > 0


def test_plot_draw_contours_linear_scale(test_geomap):
    """draw_contours=True with log_scale=False exercises the linear contour path."""
    ax, _ = test_geomap.plot(flavor=Flavor.X, draw_contours=True, log_scale=False)
    assert isinstance(ax, GeoAxes)


def test_plot_contours_without_blur(test_geomap):
    """contour_blur_sigma=0 should skip smoothing but still draw the map."""
    ax, mesh = test_geomap.plot(
        flavor=Flavor.X, draw_contours=True, contour_blur_sigma=0
    )
    assert isinstance(mesh, QuadMesh)
