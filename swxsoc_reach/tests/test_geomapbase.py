import numpy as np
from astropy import units as u
from astropy.coordinates import EarthLocation

from swxsoc_reach.geomap import GenericGeoMap


def test_geomap_world_pixel_roundtrip():
    data = np.arange(12).reshape(3, 4)
    m = GenericGeoMap(data, meta={"extent": (-180.0, 180.0, -90.0, 90.0)})

    x, y = m.world_to_pixel(0.0, 0.0)
    world = m.pixel_to_world(x, y)
    x2, y2 = m.world_to_pixel(
        EarthLocation.from_geodetic(0.0 * u.deg, 0.0 * u.deg, 0.0 * u.m)
    )

    assert isinstance(x, int)
    assert isinstance(y, int)
    assert isinstance(world, EarthLocation)
    assert -180.0 <= world.lon.to_value(u.deg) <= 180.0
    assert -90.0 <= world.lat.to_value(u.deg) <= 90.0
    assert isinstance(x2, int)
    assert isinstance(y2, int)


def test_geomap_submap_and_resample():
    data = np.arange(100).reshape(10, 10)
    m = GenericGeoMap(data, meta={"extent": (-180.0, 180.0, -90.0, 90.0)})

    sub = m.submap(lon_range=(-30.0, 30.0), lat_range=(-20.0, 20.0))
    assert sub.shape[0] > 0
    assert sub.shape[1] > 0

    r = sub.resample((5, 6))
    assert r.shape == (5, 6)


def test_geomap_wrap_longitude_sorts_columns():
    data = np.arange(12).reshape(3, 4)
    lon = np.array([170.0, 175.0, -179.0, -175.0])
    lat = np.array([-10.0, 0.0, 10.0])

    m = GenericGeoMap(data, lon=lon, lat=lat)
    wrapped = m.wrap_longitude(center=0.0)

    wrapped_lon, _ = wrapped.lon_lat_grid()
    row = wrapped_lon[wrapped.shape[0] // 2, :]
    assert np.all(np.diff(row) >= 0)


def test_geomap_plot_smoke():
    data = np.arange(20).reshape(4, 5)
    m = GenericGeoMap(data, meta={"title": "Smoke"})

    ax, artist = m.plot(use_world_coordinates=False, add_colorbar=False)
    assert ax is not None
    assert artist is not None
