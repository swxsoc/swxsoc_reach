import pytest
from astropy import units as u

from swxsoc_reach import _test_file_track
from swxsoc_reach.geomap import GenericGeoMap
from swxsoc_reach.track.trackbase import REACHTrack
from swxsoc_reach.util.enums import Flavor


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


def test_lon_lat_grid_with_1d_arrays(test_geomap):
    """lon_lat_grid should meshgrid 1D lon/lat arrays."""
    lon2d, lat2d = test_geomap.lon_lat_grid
    assert lon2d.shape == test_geomap.shape
    assert lat2d.shape == test_geomap.shape
