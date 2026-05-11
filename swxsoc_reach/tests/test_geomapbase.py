import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.nddata import NDData
from astropy.timeseries import TimeSeries

from swxsoc_reach.geomap import GenericGeoMap
from swxsoc_reach.util.schema import REACHDataSchema


def _make_test_geomap(nx=10, ny=8) -> GenericGeoMap:
    """Create a minimal GenericGeoMap for testing."""
    ts = TimeSeries(time=["2026-01-01T00:00:00", "2026-01-01T00:01:00"])
    ts.time.meta = {"CATDESC": "Observation Time", "VAR_TYPE": "support_data"}

    lon_bins = np.linspace(-180, 180, nx)
    lat_bins = np.linspace(-90, 90, ny)
    map_data = (
        np.random.rand(2, ny, nx) * 10 + 1e-6
    )  # Small positive values, 2 time samples

    variables = {
        "map_data": NDData(
            data=map_data,
            unit=u.rad / u.s,
            meta={
                "CATDESC": "Dose rate",
                "VAR_TYPE": "data",
                "DEPEND_0": "Epoch",
            },
        ),
        "lon": NDData(
            data=lon_bins,
            unit=u.deg,
            meta={"CATDESC": "Longitude", "VAR_TYPE": "support_data"},
        ),
        "lat": NDData(
            data=lat_bins,
            unit=u.deg,
            meta={"CATDESC": "Latitude", "VAR_TYPE": "support_data"},
        ),
        "regions": NDData(
            data=np.array(["SAA", "Polar Cap", "Outer Zone"], dtype="U"),
            meta={"CATDESC": "Region labels", "VAR_TYPE": "metadata"},
        ),
    }

    schema = REACHDataSchema()
    meta = dict(schema.default_global_attributes)
    meta["Flavor"] = "test_flavor"
    meta["coordinate_system"] = "geodetic"
    # Ensure required SWXData fields are set
    meta["Data_level"] = "L2"
    meta["Data_version"] = "1.0.0"
    meta["Descriptor"] = "test"

    return GenericGeoMap(
        timeseries=ts,
        support=variables,
        meta=meta,
        schema=schema,
    )


@pytest.fixture
def test_geomap():
    return _make_test_geomap()


def test_map_data_property_removes_singleton_time_axis(test_geomap):
    """map_data should not squeeze non-singleton time dimension."""
    # With 2 time samples, time axis is not singleton, so ndim should be 3
    assert test_geomap.map_data.ndim == 3
    assert test_geomap.map_data.shape == (2, 8, 10)


def test_shape_property(test_geomap):
    """shape property should return spatial shape (last 2 dims when time is present)."""
    # shape should return just the spatial dimensions, not including time axis
    assert test_geomap.shape == (8, 10)


def test_dimensions_property_equals_shape(test_geomap):
    """dimensions is an alias for shape and returns spatial dimensions."""
    assert test_geomap.dimensions == test_geomap.shape


def test_regions_property(test_geomap):
    """regions should return list of region names."""
    regions = test_geomap.regions
    assert isinstance(regions, np.ndarray)
    assert len(regions) == 3
    assert "SAA" in regions


def test_flavor_property(test_geomap):
    """flavor should return Flavor from metadata."""
    assert test_geomap.flavor == "test_flavor"


def test_coordinate_system_property(test_geomap):
    """coordinate_system should return value from metadata."""
    assert test_geomap.coordinate_system == "geodetic"


def test_extent_property(test_geomap):
    """extent should return (lon_min, lon_max, lat_min, lat_max)."""
    lon_min, lon_max, lat_min, lat_max = test_geomap.extent
    assert lon_min == pytest.approx(-180)
    assert lon_max == pytest.approx(180)
    assert lat_min == pytest.approx(-90)
    assert lat_max == pytest.approx(90)


def test_lon_lat_grid_with_1d_arrays(test_geomap):
    """lon_lat_grid should meshgrid 1D lon/lat arrays."""
    lon2d, lat2d = test_geomap.lon_lat_grid()
    assert lon2d.shape == test_geomap.shape
    assert lat2d.shape == test_geomap.shape


def test_pixel_to_world_center(test_geomap):
    """pixel_to_world at center should give expected coordinates."""
    x, y = test_geomap.shape[1] / 2, test_geomap.shape[0] / 2
    loc = test_geomap.pixel_to_world(x, y)
    assert isinstance(loc, EarthLocation)
    assert -180 <= float(loc.lon.to_value(u.deg)) <= 180
    assert -90 <= float(loc.lat.to_value(u.deg)) <= 90


def test_pixel_to_world_clipping(test_geomap):
    """pixel_to_world should clip out-of-bounds pixel coordinates."""
    loc1 = test_geomap.pixel_to_world(-100, -100)
    loc2 = test_geomap.pixel_to_world(1000, 1000)
    # Both should map to valid coordinates within bounds
    assert -180 <= float(loc1.lon.to_value(u.deg)) <= 180
    assert -90 <= float(loc1.lat.to_value(u.deg)) <= 90
    assert -180 <= float(loc2.lon.to_value(u.deg)) <= 180
    assert -90 <= float(loc2.lat.to_value(u.deg)) <= 90


def test_world_to_pixel_with_lon_lat(test_geomap):
    """world_to_pixel with lon/lat floats should return pixel indices."""
    x, y = test_geomap.world_to_pixel(0.0, 0.0)
    assert 0 <= x < test_geomap.shape[1]
    assert 0 <= y < test_geomap.shape[0]


def test_world_to_pixel_with_earthlocation(test_geomap):
    """world_to_pixel with EarthLocation should work correctly."""
    loc = EarthLocation.from_geodetic(lon=0 * u.deg, lat=0 * u.deg)
    x, y = test_geomap.world_to_pixel(loc)
    assert 0 <= x < test_geomap.shape[1]
    assert 0 <= y < test_geomap.shape[0]


def test_world_to_pixel_missing_lat_raises(test_geomap):
    """world_to_pixel without lat should raise ValueError."""
    with pytest.raises(ValueError, match="either an EarthLocation or both"):
        test_geomap.world_to_pixel(0.0)


def test_pixel_world_roundtrip_approximate(test_geomap):
    """pixel->world->pixel should be approximately consistent."""
    x1, y1 = 3.5, 4.2
    loc = test_geomap.pixel_to_world(x1, y1)
    x2, y2 = test_geomap.world_to_pixel(loc)
    # Should be close after rounding and discretization
    assert abs(x2 - round(x1)) <= 1
    assert abs(y2 - round(y1)) <= 1


def test_lon_lat_grid_dimension_mismatch_1d(test_geomap):
    """lon_lat_grid should raise if 1D arrays don't match map dimensions."""
    # Create a map with mismatched lon array size
    ts = TimeSeries(time=["2026-01-01T00:00:00", "2026-01-01T00:01:00"])
    ts.time.meta = {"CATDESC": "Observation Time", "VAR_TYPE": "support_data"}
    variables = {
        "map_data": NDData(
            data=np.random.rand(2, 8, 10),
            unit=u.rad / u.s,
            meta={"CATDESC": "Dose rate", "VAR_TYPE": "data"},
        ),
        "lon": NDData(
            data=np.linspace(-180, 180, 5),  # Wrong size
            unit=u.deg,
            meta={"CATDESC": "Longitude", "VAR_TYPE": "support_data"},
        ),
        "lat": NDData(
            data=np.linspace(-90, 90, 8),
            unit=u.deg,
            meta={"CATDESC": "Latitude", "VAR_TYPE": "support_data"},
        ),
    }
    schema = REACHDataSchema()
    meta = dict(schema.default_global_attributes)
    meta["Data_level"] = "L2"
    meta["Data_version"] = "1.0.0"
    meta["Descriptor"] = "test"
    geomap = GenericGeoMap(timeseries=ts, support=variables, meta=meta, schema=schema)
    with pytest.raises(ValueError, match="coordinate lengths must match"):
        geomap.lon_lat_grid()
