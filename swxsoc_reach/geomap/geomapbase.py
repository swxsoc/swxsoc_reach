"""Generic geospatial map container with SunPy-like map helpers."""

import astropy.units as u
import numpy as np
from astropy.coordinates import EarthLocation
from astropy.nddata import NDData
from astropy.timeseries import TimeSeries
from swxsoc import log
from swxsoc.swxdata import SWXData

from swxsoc_reach.util.schema import REACHDataSchema
from swxsoc_reach.util.util import load_regions
from swxsoc_reach.visualization.viz import plot_region_code_contours_on_geomap

from ..util.enums import Flavor, SensorId


class GenericGeoMap(SWXData):
    """A generic 2D geospatial map object.

    This class provides a compact, SunPy-like API for geospatial grids:

    - map metadata in ``meta``
    - data access via ``data`` / ``unit``
    - pixel/world coordinate conversion helpers
    - submap extraction and nearest-neighbor resampling
    - a built-in plotting method for quick visualization

    Parameters
    ----------
    data : numpy.ndarray
        2D geospatial data array.
    meta : dict | None, optional
        Metadata for the map (title, coordinate system, extent, etc.).
    mask : numpy.ndarray | None, optional
        Optional mask array broadcastable to ``data``.
    unit : str | None, optional
        Unit label for map values.
    lon : numpy.ndarray | None, optional
        1D or 2D longitudes in degrees.
    lat : numpy.ndarray | None, optional
        1D or 2D latitudes in degrees.
    """

    def __init__(
        self,
        data: np.ndarray,
        meta: dict[str, str] | None = None,
        *,
        timeseries: TimeSeries | None = None,
        data_version: str = "1.0.0",
        data_level: str = "L1C>Level 1 Calibrated",
        global_attrs: dict | None = None,
        mask: np.ndarray | None = None,
        unit: str | None = None,
        lon: np.ndarray | None = None,
        lat: np.ndarray | None = None,
        flavor: Flavor | None = None,
    ):
        from astropy.time import Time
        from astropy.timeseries import TimeSeries

        # Build a minimal TimeSeries for SWXData if none provided.
        # Two entries are required by REACHDataSchema._get_resolution.
        if timeseries is None:
            timeseries = TimeSeries(
                {
                    "time": Time(
                        ["2000-01-01T00:00:00", "2000-01-01T00:00:05"],
                        format="isot",
                        scale="utc",
                    )
                }
            )

        # Build SWXData global metadata from schema defaults
        _swx_meta = dict(REACHDataSchema().default_global_attributes)
        # Override Data_level to a value accepted by the mission config
        # (default 'L1>Level 1' maps to 'l1' which is not in valid_data_levels)
        _swx_meta["Data_level"] = data_level
        _swx_meta["Data_version"] = data_version
        if global_attrs is not None:
            _swx_meta.update(global_attrs)

        arr = np.asarray(data)
        if arr.ndim != 2:
            raise ValueError(
                f"GenericGeoMap expects 2D data, got array with shape {arr.shape}."
            )

        _map_arr = np.ma.array(arr, mask=mask, copy=True)
        _map_nddata = NDData(
            data=_map_arr,
            mask=np.ma.getmaskarray(_map_arr),
            meta={
                "CATDESC": "2D geospatial map data",
                "VAR_TYPE": "support_data",
                "UNITS": unit if unit is not None else "",
            },
        )

        # Set _map_meta BEFORE super().__init__() because _derive_metadata()
        # may call self.meta (which returns _map_meta) during initialization.
        self._map_meta = dict(meta) if meta is not None else {}

        super().__init__(
            timeseries=timeseries,
            support={"map_data": _map_nddata},
            meta=_swx_meta,
            schema=REACHDataSchema(),
        )

        self._unit = unit
        self.plot_settings = {
            "cmap": self._map_meta.get("cmap", "viridis"),
            "origin": self._map_meta.get("origin", "lower"),
        }

        self._lon = None if lon is None else np.asarray(lon, dtype=float)
        self._lat = None if lat is None else np.asarray(lat, dtype=float)
        self.flavor = flavor
        self._validate_coordinates()

    def __repr__(self) -> str:
        title = self._map_meta.get("title", "Untitled")
        coord_sys = self.coordinate_system
        return (
            f"GenericGeoMap(title={title!r}, shape={self.shape}, "
            f"coordinate_system={coord_sys!r}, unit={self.unit!r})"
        )

    @property
    def map_data(self) -> np.ma.MaskedArray:
        """Map data as a masked 2D array, stored as NDData in SWXData support."""
        nd = self._support["map_data"]
        arr = np.asarray(nd.data)
        mask = nd.mask if nd.mask is not None else False
        return np.ma.array(arr, mask=mask)

    @property
    def map_meta(self) -> dict[str, str]:
        """Map-specific metadata dictionary."""
        return self._map_meta

    @property
    def unit(self) -> str | None:
        """Unit label for map values."""
        return self._unit

    @property
    def quantity(self):
        """Data as an astropy Quantity when astropy is available."""
        if self._unit is None or u is None:
            return self.map_data
        return np.asarray(self.map_data) * u.Unit(self._unit)

    @property
    def shape(self) -> tuple[int, int]:
        """Map shape as ``(ny, nx)``."""
        return self.map_data.shape

    @property
    def dimensions(self) -> tuple[int, int]:
        """Alias for shape, kept for SunPy-style familiarity."""
        return self.shape

    @property
    def coordinate_system(self) -> str:
        """Coordinate system label for this map."""
        return str(self._map_meta.get("coordinate_system", "geodetic"))

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """Map extent as lon/lat min-max values in degrees."""
        if "extent" in self._map_meta:
            lon_min, lon_max, lat_min, lat_max = self._map_meta["extent"]
            return (
                float(lon_min),
                float(lon_max),
                float(lat_min),
                float(lat_max),
            )

        lon2d, lat2d = self.lon_lat_grid()
        return (
            float(np.nanmin(lon2d)),
            float(np.nanmax(lon2d)),
            float(np.nanmin(lat2d)),
            float(np.nanmax(lat2d)),
        )

    def copy(self) -> "GenericGeoMap":
        """Return a deep-ish copy of the map data and metadata."""
        _md = self.map_data
        return GenericGeoMap(
            np.asarray(_md),
            dict(self._map_meta),
            timeseries=self._timeseries[self._default_timeseries_key].copy(),
            mask=np.ma.getmaskarray(_md),
            unit=self._unit,
            lon=None if self._lon is None else self._lon.copy(),
            lat=None if self._lat is None else self._lat.copy(),
        )

    def lon_lat_grid(self) -> tuple[np.ndarray, np.ndarray]:
        """Return 2D longitude and latitude grids in degrees."""
        ny, nx = self.shape

        if self._lon is not None and self._lat is not None:
            if self._lon.ndim == 1 and self._lat.ndim == 1:
                if self._lon.size != nx or self._lat.size != ny:
                    raise ValueError(
                        "1D longitude/latitude coordinate lengths must match map shape."
                    )
                lon2d, lat2d = np.meshgrid(self._lon, self._lat)
                return lon2d, lat2d

            if self._lon.ndim == 2 and self._lat.ndim == 2:
                if self._lon.shape != self.shape or self._lat.shape != self.shape:
                    raise ValueError(
                        "2D longitude/latitude arrays must match map shape."
                    )
                return self._lon, self._lat

            raise ValueError("lon and lat must both be 1D or both be 2D arrays.")

        lon_min, lon_max, lat_min, lat_max = self.extent_from_shape()
        lon_axis = np.linspace(lon_min, lon_max, nx)
        lat_axis = np.linspace(lat_min, lat_max, ny)
        lon2d, lat2d = np.meshgrid(lon_axis, lat_axis)
        return lon2d, lat2d

    def extent_from_shape(self) -> tuple[float, float, float, float]:
        """Infer extent from metadata or default global geodetic bounds."""
        if "extent" in self._map_meta:
            lon_min, lon_max, lat_min, lat_max = self._map_meta["extent"]
            return (
                float(lon_min),
                float(lon_max),
                float(lat_min),
                float(lat_max),
            )
        return -180.0, 180.0, -90.0, 90.0

    def pixel_to_world(self, x: float, y: float):
        """Convert zero-based pixel coordinates to an EarthLocation."""
        if EarthLocation is None or u is None:
            raise ImportError(
                "pixel_to_world requires astropy.coordinates.EarthLocation."
            )

        x_idx = int(np.clip(round(x), 0, self.shape[1] - 1))
        y_idx = int(np.clip(round(y), 0, self.shape[0] - 1))
        lon2d, lat2d = self.lon_lat_grid()
        return EarthLocation.from_geodetic(
            lon=float(lon2d[y_idx, x_idx]) * u.deg,
            lat=float(lat2d[y_idx, x_idx]) * u.deg,
            height=0.0 * u.m,
        )

    def world_to_pixel(
        self,
        location_or_lon,
        lat: float | None = None,
    ) -> tuple[int, int]:
        """Convert EarthLocation or lon/lat values to pixel indices."""
        if EarthLocation is not None and isinstance(location_or_lon, EarthLocation):
            lon_value = float(location_or_lon.lon.to_value(u.deg))
            lat_value = float(location_or_lon.lat.to_value(u.deg))
        else:
            if lat is None:
                raise ValueError(
                    "Pass either an EarthLocation or both lon and lat values."
                )
            lon_value = float(location_or_lon)
            lat_value = float(lat)

        lon2d, lat2d = self.lon_lat_grid()
        distance2 = (lon2d - lon_value) ** 2 + (lat2d - lat_value) ** 2
        y_idx, x_idx = np.unravel_index(
            np.nanargmin(distance2),
            distance2.shape,
        )
        return int(x_idx), int(y_idx)

    def submap(
        self,
        lon_range: tuple[float, float],
        lat_range: tuple[float, float],
    ) -> "GenericGeoMap":
        """Extract a submap bounded by longitude and latitude ranges."""
        lon_min, lon_max = sorted(lon_range)
        lat_min, lat_max = sorted(lat_range)

        lon2d, lat2d = self.lon_lat_grid()
        inside = (
            (lon2d >= lon_min)
            & (lon2d <= lon_max)
            & (lat2d >= lat_min)
            & (lat2d <= lat_max)
        )

        if not np.any(inside):
            raise ValueError("Requested submap bounds do not overlap the map domain.")

        rows, cols = np.where(inside)
        y0, y1 = rows.min(), rows.max() + 1
        x0, x1 = cols.min(), cols.max() + 1

        _md = self.map_data
        sub_data = _md[y0:y1, x0:x1]
        sub_lon = lon2d[y0:y1, x0:x1]
        sub_lat = lat2d[y0:y1, x0:x1]
        sub_meta = dict(self._map_meta)
        sub_meta["extent"] = (
            float(np.nanmin(sub_lon)),
            float(np.nanmax(sub_lon)),
            float(np.nanmin(sub_lat)),
            float(np.nanmax(sub_lat)),
        )
        return GenericGeoMap(
            np.asarray(sub_data),
            meta=sub_meta,
            timeseries=self._timeseries[self._default_timeseries_key].copy(),
            mask=np.ma.getmaskarray(sub_data),
            unit=self._unit,
            lon=sub_lon,
            lat=sub_lat,
        )

    def resample(self, dimensions: tuple[int, int]) -> "GenericGeoMap":
        """Return a nearest-neighbor resampled map with new dimensions."""
        ny_new, nx_new = dimensions
        if ny_new <= 0 or nx_new <= 0:
            raise ValueError("resample dimensions must be positive.")

        ny_old, nx_old = self.shape
        y_index = np.clip(
            np.round(np.linspace(0, ny_old - 1, ny_new)).astype(int),
            0,
            ny_old - 1,
        )
        x_index = np.clip(
            np.round(np.linspace(0, nx_old - 1, nx_new)).astype(int),
            0,
            nx_old - 1,
        )

        _md = self.map_data
        data_resampled = _md[np.ix_(y_index, x_index)]
        lon2d, lat2d = self.lon_lat_grid()
        lon_resampled = lon2d[np.ix_(y_index, x_index)]
        lat_resampled = lat2d[np.ix_(y_index, x_index)]

        resampled_meta = dict(self._map_meta)
        resampled_meta["extent"] = (
            float(np.nanmin(lon_resampled)),
            float(np.nanmax(lon_resampled)),
            float(np.nanmin(lat_resampled)),
            float(np.nanmax(lat_resampled)),
        )

        return GenericGeoMap(
            np.asarray(data_resampled),
            meta=resampled_meta,
            timeseries=self._timeseries[self._default_timeseries_key].copy(),
            mask=np.ma.getmaskarray(data_resampled),
            unit=self._unit,
            lon=lon_resampled,
            lat=lat_resampled,
        )

    def wrap_longitude(self, center: float = 0.0) -> "GenericGeoMap":
        """Wrap longitudes around ``center`` and reorder map columns."""
        lon2d, lat2d = self.lon_lat_grid()
        wrapped_lon = ((lon2d - center + 180.0) % 360.0) - 180.0 + center

        column_order = np.argsort(wrapped_lon[self.shape[0] // 2, :])
        _md = self.map_data
        wrapped_data = _md[:, column_order]
        wrapped_lon = wrapped_lon[:, column_order]
        wrapped_lat = lat2d[:, column_order]

        wrapped_meta = dict(self._map_meta)
        wrapped_meta["extent"] = (
            float(np.nanmin(wrapped_lon)),
            float(np.nanmax(wrapped_lon)),
            float(np.nanmin(wrapped_lat)),
            float(np.nanmax(wrapped_lat)),
        )

        return GenericGeoMap(
            np.asarray(wrapped_data),
            meta=wrapped_meta,
            timeseries=self._timeseries[self._default_timeseries_key].copy(),
            mask=np.ma.getmaskarray(wrapped_data),
            unit=self._unit,
            lon=wrapped_lon,
            lat=wrapped_lat,
        )

    def plot(
        self,
        ax=None,
        *,
        add_colorbar: bool = True,
        use_world_coordinates: bool = True,
        **kwargs,
    ):
        """Plot this map with matplotlib and return ``(ax, artist)``."""
        import matplotlib as mpl
        import matplotlib.pyplot as plt

        try:
            from cartopy import crs as ccrs

            has_cartopy = True
        except Exception:
            has_cartopy = False

        colorbarmax = -2
        colorbarmin = -7

        # Make the colorblind friendly colormaps
        # These colors work well for all be true black white colorblind
        cdi = "#093145"
        cli = "#3c6478"
        cda = "#107896"
        cla = "#43abc9"
        cdk = "#829356"
        clk = "#b5c689"
        cdd = "#bca136"
        cld = "#efd469"
        cdc = "#c2571a"
        clc = "#f58b4c"
        cdr = "#9a2617"
        clr = "#cd594a"
        clg = "#F3F4F6"
        cdg = "#8B8E95"

        greycolors = [clg, cdg]
        greencolors = [clg, clk, cdk]
        yellowcolors = [clg, cld, cdd]
        redcolors = [clg, clr, cdr]
        hotcolors = [cld, cdd, cdc, cdr]
        colors = [cdi, cdk, cld, cdc, cdr]
        bluecolors = [clg, cla, cda, cdi]

        bluemap = mpl.colors.LinearSegmentedColormap.from_list("", bluecolors)
        pltmap = mpl.colors.LinearSegmentedColormap.from_list("", hotcolors)
        greenmap = mpl.colors.LinearSegmentedColormap.from_list("", greencolors)
        yellowmap = mpl.colors.LinearSegmentedColormap.from_list("", yellowcolors)
        redmap = mpl.colors.LinearSegmentedColormap.from_list("", redcolors)

        lookuplon, lookuplat, glook = load_regions()

        # Create 2D region grid
        _md = self.map_data
        region_grid = np.zeros(_md.shape, dtype=int)
        lon_indices = ((lookuplon + 180) % 360).astype(int)
        lat_indices = (lookuplat + 90).astype(int)
        region_grid[lat_indices, lon_indices] = glook

        # Assign to regions using masks
        SAA = np.zeros(_md.shape) * np.nan
        PC = np.zeros(_md.shape) * np.nan
        outrad = np.zeros(_md.shape) * np.nan
        slot = np.zeros(_md.shape) * np.nan
        for region_code in np.unique(glook):
            mask = region_grid == region_code
            if region_code in (1, -1):  # SAA and Inner Zone
                SAA[mask] = _md[mask]
            elif region_code in (2, -2):  # Polar Cap
                PC[mask] = _md[mask]
            elif region_code in (3, -3):  # Outer Zone
                outrad[mask] = _md[mask]
            elif region_code in (4, -4):  # Slot
                slot[mask] = _md[mask]

        if ax is None:
            fig = plt.figure(figsize=(11.69, 8.27))
            if has_cartopy:
                ax = plt.subplot(
                    1,
                    1,
                    1,
                    projection=ccrs.PlateCarree(central_longitude=0),
                )
            else:
                ax = plt.subplot(1, 1, 1)
        else:
            fig = ax.figure

        if has_cartopy:
            plot_region_code_contours_on_geomap(
                ax=ax,
                draw_coastlines=True,
                draw_gridlines=True,
                label_contours=False,
            )
        xylon = self.lon_lat_grid()[0]
        xylat = self.lon_lat_grid()[1]
        mapSAA = ax.pcolormesh(
            xylon,
            xylat,
            np.log10(SAA),
            vmin=colorbarmin,
            vmax=colorbarmax,
            cmap=redmap,
        )
        mapPC = ax.pcolormesh(
            xylon,
            xylat,
            np.log10(PC),
            vmin=colorbarmin,
            vmax=colorbarmax,
            cmap=yellowmap,
        )
        mapout = ax.pcolormesh(
            xylon,
            xylat,
            np.log10(outrad),
            vmin=colorbarmin,
            vmax=colorbarmax,
            cmap=bluemap,
        )
        mapslot = ax.pcolormesh(
            xylon,
            xylat,
            np.log10(slot),
            vmin=colorbarmin,
            vmax=colorbarmax,
            cmap=greenmap,
        )

        title_pre = self._map_meta["map_fields"]["plotTitlePre"]
        pltdos = self._map_meta["map_fields"].get("pltdos", "")

        pltname = f"{self.flavor} {pltdos}".strip()

        ax.set_title(
            (title_pre + pltname).strip(),
            fontdict={"fontsize": 15},
        )

        if add_colorbar:
            intticks = int(np.floor(colorbarmax - colorbarmin) + 1)
            tickemptylabels = [" " for _ in range(intticks)]

            pos = ax.get_position()
            cbar_height = 0.03
            cbar_width = pos.width
            cbar_x = pos.x0
            cbar_y = pos.y0 - 0.08

            cax_saa = fig.add_axes((cbar_x, cbar_y, cbar_width, cbar_height))
            cbarSAA = fig.colorbar(
                mapSAA,
                cax=cax_saa,
                orientation="horizontal",
            )
            cbarSAA.ax.set_xticklabels(tickemptylabels)
            cbarSAA.ax.tick_params(direction="in")
            cbarSAA.ax.text(
                0.01,
                0.5,
                "SAA and Inner Zone",
                transform=cbarSAA.ax.transAxes,
                ha="left",
                va="center",
                color="black",
                fontsize=9,
                weight="bold",
            )

            cbar_y -= cbar_height
            cax_out = fig.add_axes((cbar_x, cbar_y, cbar_width, cbar_height))
            cbarout = fig.colorbar(
                mapout,
                cax=cax_out,
                orientation="horizontal",
            )
            cbarout.ax.set_xticklabels(tickemptylabels)
            cbarout.ax.tick_params(direction="in")
            cbarout.ax.text(
                0.01,
                0.5,
                "Outer Zone",
                transform=cbarout.ax.transAxes,
                ha="left",
                va="center",
                color="black",
                fontsize=9,
                weight="bold",
            )

            cbar_y -= cbar_height
            cax_slot = fig.add_axes((cbar_x, cbar_y, cbar_width, cbar_height))
            cbarslot = fig.colorbar(
                mapslot,
                cax=cax_slot,
                orientation="horizontal",
            )
            cbarslot.ax.set_xticklabels(tickemptylabels)
            cbarslot.ax.tick_params(direction="in")
            cbarslot.ax.text(
                0.01,
                0.5,
                "Slot",
                transform=cbarslot.ax.transAxes,
                ha="left",
                va="center",
                color="black",
                fontsize=9,
                weight="bold",
            )

            cbar_y -= cbar_height
            cax_pc = fig.add_axes((cbar_x, cbar_y, cbar_width, cbar_height))
            cbarPC = fig.colorbar(
                mapPC,
                cax=cax_pc,
                orientation="horizontal",
            )
            cbarPC.ax.tick_params(direction="in")
            cbarPC.ax.text(
                0.01,
                0.5,
                "Polar Cap",
                transform=cbarPC.ax.transAxes,
                ha="left",
                va="center",
                color="black",
                fontsize=9,
                weight="bold",
            )
            cbarPC.set_label("log (rad/sec)", fontsize=10, labelpad=5)
            cbarPC.ax.xaxis.set_label_position("bottom")
        plt.show()
        return ax, mapPC

    def _validate_coordinates(self) -> None:
        """Validate user-provided longitude/latitude arrays, if provided."""
        if getattr(self, "_lon", None) is None and getattr(self, "_lat", None) is None:
            return
        if (self._lon is None) ^ (self._lat is None):
            raise ValueError(
                "lon and lat must either both be provided or both be None."
            )
        if self._lon is None:
            return

        lon = self._lon
        lat = self._lat
        if lat is None:
            raise ValueError("lat cannot be None when lon is provided.")

        if lon.ndim != lat.ndim:
            raise ValueError("lon and lat must have the same dimensionality.")
        if lon.ndim not in (1, 2):
            raise ValueError("lon and lat must be 1D or 2D arrays.")

        if lon.ndim == 1:
            if lon.size != self.shape[1] or lat.size != self.shape[0]:
                raise ValueError(
                    "For 1D coordinates, lon length must match nx and "
                    "lat length must match ny."
                )
        else:
            if lon.shape != self.shape or lat.shape != self.shape:
                raise ValueError(
                    "For 2D coordinates, lon and lat must match map shape."
                )
