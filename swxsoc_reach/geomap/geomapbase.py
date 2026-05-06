"""Generic geospatial map container with SunPy-like map helpers."""

import astropy.units as u
import numpy as np
from astropy.coordinates import EarthLocation
from swxsoc.swxdata import SWXData

from swxsoc_reach.visualization.viz import plot_region_code_contours_on_geomap

from ..util.enums import Flavor, Region


class GenericGeoMap(SWXData):
    """A generic 2D geospatial map object.

    This class provides a compact, SunPy-like API for geospatial grids:

    """

    @property
    def map_data(self) -> np.ndarray:
        """2D geospatial data array."""
        return self.support["map_data"].data

    @property
    def _lon(self) -> np.ndarray:
        """Longitude coordinate array (1D or 2D) in degrees, or None if not provided."""
        if "lon" in self.support:
            return self.support["lon"].data
        return None

    @property
    def _lat(self) -> np.ndarray:
        """Latitude coordinate array (1D or 2D) in degrees, or None if not provided."""
        if "lat" in self.support:
            return self.support["lat"].data
        return None

    @property
    def flavor(self) -> Flavor:
        pass

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
        return str(self.meta.get("coordinate_system", "geodetic"))

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """Map extent as lon/lat min-max values in degrees."""
        return (
            float(self._lon.min()),
            float(self._lon.max()),
            float(self._lat.min()),
            float(self._lat.max()),
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
        pass

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

        pass

    def plot(
        self,
        ax=None,
        *,
        add_colorbar: bool = True,
        color_by_region: bool = True,
        **kwargs,
    ):
        """Plot this map with matplotlib and return ``(ax, artist)``.

        Parameters
        ----------
        color_by_region : bool, optional
            When ``True`` (default) the data is split into per-region arrays
            and each region is drawn with its own colormap.  When ``False`` the
            full map data is plotted as a single ``pcolormesh`` using the
            ``viridis`` colormap.
        """
        import matplotlib as mpl
        import matplotlib.pyplot as plt

        try:
            from cartopy import crs as ccrs

            has_cartopy = True
        except Exception:
            has_cartopy = False

        colorbarmax = -2
        colorbarmin = -7

        # Colorblind-friendly colormaps
        cdi = "#093145"
        cla = "#43abc9"
        cda = "#107896"
        clg = "#F3F4F6"
        cdk = "#829356"
        clk = "#b5c689"
        cdd = "#bca136"
        cld = "#efd469"
        cdr = "#9a2617"
        clr = "#cd594a"

        bluemap = mpl.colors.LinearSegmentedColormap.from_list("", [clg, cla, cda, cdi])
        greenmap = mpl.colors.LinearSegmentedColormap.from_list("", [clg, clk, cdk])
        yellowmap = mpl.colors.LinearSegmentedColormap.from_list("", [clg, cld, cdd])
        redmap = mpl.colors.LinearSegmentedColormap.from_list("", [clg, clr, cdr])

        # Split map data into per-region arrays using the pre-computed mask
        # stored by to_geomap(). Shape: (nregions, nlat, nlon).
        _md = self.map_data
        xylon, xylat = self.lon_lat_grid()

        region_mask = self["mask"].data

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

        import warnings

        # Cartopy's GridLiner calls set_ticklabels() without a FixedLocator,
        # which produces a UserWarning in recent matplotlib versions.  Suppress it.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="set_ticklabels\\(\\) should only be used with a fixed number",
                category=UserWarning,
            )
            plot_region_code_contours_on_geomap(
                ax=ax,
                draw_coastlines=True,
                draw_gridlines=True,
                label_contours=False,
            )

        time_str = (
            np.min(self.time).strftime("%d %b %Y %H:%M")
            + " - "
            + np.max(self.time).strftime("%d %b %Y %H:%M")
        )
        ax.set_title(f"{time_str} - Flavor {self.flavor}")

        if color_by_region:
            region_cmaps = {
                Region.SAA: redmap,
                Region.POLAR_CAP: yellowmap,
                Region.OUTER_ZONE: bluemap,
                Region.SLOT: greenmap,
            }
            regions = [
                (region, region_cmaps[region], region.label)
                for region in Region.ordered()
            ]

            meshes = []
            for region, cmap, _ in regions:
                region_data = np.where(region_mask[region.mask_index], _md, np.nan)
                with np.errstate(divide="ignore", invalid="ignore"):
                    log_data = np.where(region_data > 0, np.log10(region_data), np.nan)
                mesh = ax.pcolormesh(
                    xylon,
                    xylat,
                    log_data,
                    vmin=colorbarmin,
                    vmax=colorbarmax,
                    cmap=cmap,
                )
                meshes.append(mesh)

            if add_colorbar:
                intticks = int(np.floor(colorbarmax - colorbarmin) + 1)
                tickemptylabels = [" " for _ in range(intticks)]

                pos = ax.get_position()
                cbar_height = 0.03
                cbar_width = pos.width
                cbar_x = pos.x0
                cbar_y = pos.y0 - 0.08

                for i, (mesh, (_, _, label)) in enumerate(zip(meshes, regions)):
                    cax = fig.add_axes((cbar_x, cbar_y, cbar_width, cbar_height))
                    cbar = fig.colorbar(mesh, cax=cax, orientation="horizontal")
                    cbar.ax.tick_params(direction="in")
                    cbar.ax.text(
                        0.01,
                        0.5,
                        label,
                        transform=cbar.ax.transAxes,
                        ha="left",
                        va="center",
                        color="black",
                        fontsize=9,
                        weight="bold",
                    )
                    if i < len(regions) - 1:
                        cbar.ax.set_xticklabels(tickemptylabels)
                    else:
                        cbar.set_label("log (rad/sec)", fontsize=10, labelpad=5)
                        cbar.ax.xaxis.set_label_position("bottom")
                    cbar_y -= cbar_height

            last_mesh = meshes[-1]
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                log_data = np.where(_md > 0, np.log10(_md), np.nan)
            last_mesh = ax.pcolormesh(
                xylon,
                xylat,
                log_data,
                vmin=colorbarmin,
                vmax=colorbarmax,
                cmap="viridis",
            )
            if add_colorbar:
                fig.colorbar(
                    last_mesh, ax=ax, label="log (rad/sec)", orientation="horizontal"
                )

        plt.show()
        return ax, last_mesh

    def sum_per_region(self) -> dict[str, float]:
        """Return the sum of all map pixels within each region.

        The mask stored by :meth:`~swxsoc_reach.track.trackbase.REACHTrack.to_geomap`
        is used directly, so no contour-path computation is needed here.

        Returns
        -------
        dict
            Keys are region keys (``"saa"``, ``"polar_cap"``,
            ``"outer_zone"``, ``"slot"``); values are the sum of finite
            ``map_data`` pixels that fall inside that region.  NaN pixels
            are excluded from the sum.
        """
        region_mask = self["mask"].data  # shape (nregions, nlat, nlon)
        _md = self.map_data

        result: dict[str, float] = {}
        for region in Region.ordered():
            masked = np.where(region_mask[region.mask_index], _md, np.nan)
            result[region.key] = float(np.nansum(masked))
        return result

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
