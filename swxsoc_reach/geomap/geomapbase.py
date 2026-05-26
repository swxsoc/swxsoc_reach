"""Generic geospatial map container with SunPy-like map helpers."""

import warnings
from pathlib import Path

import astropy.units as u
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import EarthLocation
from cartopy import crs as ccrs
from swxsoc.swxdata import SWXData

from swxsoc_reach.util.enums import Flavor, Region
from swxsoc_reach.util.schema import REACHDataSchema
from swxsoc_reach.visualization.viz import plot_geomap

# REACH dose data routinely contains zeros / non-positive values; log10 of
# these is mathematically undefined but expected, so silence the resulting
# RuntimeWarnings for this module only.
warnings.filterwarnings(
    "ignore",
    message="divide by zero encountered in log10",
    category=RuntimeWarning,
    module=__name__,
)
warnings.filterwarnings(
    "ignore",
    message="invalid value encountered in log10",
    category=RuntimeWarning,
    module=__name__,
)
# Matplotlib emits this when set_xticklabels() is called without a matching
# FixedLocator; we intentionally do that to blank out tick labels on stacked
# per-region colorbars, so the warning is noise here.
warnings.filterwarnings(
    "ignore",
    message=r"set_ticklabels\(\) should only be used with a fixed number of ticks",
    category=UserWarning,
    module=__name__,
)


class GenericGeoMap(SWXData):
    """A generic 2D geospatial map object.

    Provides a compact, SunPy-like API for geospatial dose-rate grids:
    per-statistic map accessors (``median_map``, ``mean_map``, ...),
    coordinate grid construction (``lon_lat_grid``), pixel/world
    conversions (``pixel_to_world``, ``world_to_pixel``), an aggregated
    plotter (``plot``), and per-region summaries (``sum_per_region``).

    The underlying storage is an :class:`swxsoc.swxdata.SWXData` container
    populated by
    :meth:`swxsoc_reach.track.trackbase.REACHTrack.to_geomap`. Each
    statistic map has shape ``(nflavors, ny, nx)``.
    """

    def _statistic_map(self, statistic: str) -> np.ndarray:
        """Return the requested statistic map with a leading singleton time axis squeezed.

        Parameters
        ----------
        statistic : str
            Statistic name. One of ``"median"``, ``"mean"``, ``"count"``,
            ``"min"``, ``"max"``, or ``"std"``.

        Returns
        -------
        numpy.ndarray
            Array of shape ``(nflavors, ny, nx)``.
        """
        data = self[f"{statistic}_map"].data
        if data.ndim >= 4 and data.shape[0] == 1:
            return np.squeeze(data, axis=0)
        return data

    @property
    def flavor_names(self) -> np.ndarray:
        if "dosimeter_flavor_names" not in self.support:
            return np.asarray([], dtype="U")
        return self.support["dosimeter_flavor_names"].data

    @property
    def median_map(self) -> np.ndarray:
        """Per-flavor median dose-rate map of shape ``(nflavors, ny, nx)``."""
        return self._statistic_map("median")

    @property
    def mean_map(self) -> np.ndarray:
        """Per-flavor mean dose-rate map of shape ``(nflavors, ny, nx)``."""
        return self._statistic_map("mean")

    @property
    def count_map(self) -> np.ndarray:
        """Per-flavor sample-count map of shape ``(nflavors, ny, nx)``."""
        return self._statistic_map("count")

    @property
    def min_map(self) -> np.ndarray:
        """Per-flavor minimum dose-rate map of shape ``(nflavors, ny, nx)``."""
        return self._statistic_map("min")

    @property
    def max_map(self) -> np.ndarray:
        """Per-flavor maximum dose-rate map of shape ``(nflavors, ny, nx)``."""
        return self._statistic_map("max")

    @property
    def std_map(self) -> np.ndarray:
        """Per-flavor sample standard-deviation map of shape ``(nflavors, ny, nx)``."""
        return self._statistic_map("std")

    @property
    def _lon(self) -> np.ndarray | None:
        """Longitude coordinate array (1D or 2D) in degrees, or ``None`` if not provided."""
        if "lon" in self.support:
            return self.support["lon"].data
        return None

    @property
    def _lat(self) -> np.ndarray | None:
        """Latitude coordinate array (1D or 2D) in degrees, or ``None`` if not provided."""
        if "lat" in self.support:
            return self.support["lat"].data
        return None

    @property
    def regions(self) -> np.ndarray:
        """Array of region names corresponding to the map's regions variable.

        Returns an empty list when no ``regions`` support variable is present.
        """
        if "regions" not in self.support:
            return []
        return self.support["regions"].data

    @property
    def flavor(self) -> Flavor:
        """:class:`~swxsoc_reach.util.enums.Flavor` parsed from the ``Flavor`` metadata key."""
        return Flavor.from_str(self.meta.get("Flavor"))

    @property
    def shape(self) -> tuple[int, int]:
        """Map shape as ``(ny, nx)`` - spatial dimensions only.

        Returns the spatial dimensions of the map grid, regardless of whether
        time-indexed data is present in the underlying storage. If the internal
        data includes a time axis (e.g., ``(nt, ny, nx)``), only the spatial
        dimensions are returned.

        Returns
        -------
        tuple[int, int]
            The map dimensions as ``(num_latitude, num_longitude)``.
        """
        return self.median_map.shape[1:]

    @property
    def dimensions(self) -> tuple[int, int]:
        """Alias for shape, kept for SunPy-style familiarity."""
        return self.shape

    @property
    def coordinate_system(self) -> str:
        """Coordinate system label for this map.

        Returns the name of the coordinate system used by the map's longitude
        and latitude values. Typically ``"geodetic"`` for WGS84 coordinates.
        """
        return str(self.meta.get("coordinate_system", "geodetic"))

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """Map extent as lon/lat min-max values in degrees.

        Returns
        -------
        tuple[float, float, float, float]
            Extent as ``(lon_min, lon_max, lat_min, lat_max)`` in degrees.
        """
        return (
            float(self._lon.min()),
            float(self._lon.max()),
            float(self._lat.min()),
            float(self._lat.max()),
        )

    def _flavor_index(self, flavor: Flavor | int) -> int:
        """Resolve a :class:`Flavor` (or integer index) to its position in :meth:`Flavor.ordered`.

        Parameters
        ----------
        flavor : Flavor or int
            Either a :class:`~swxsoc_reach.util.enums.Flavor` member, or an
            integer index into :meth:`Flavor.ordered`.

        Returns
        -------
        int
            Zero-based index into the ordered flavor list.

        Raises
        ------
        ValueError
            If ``flavor`` is an unrecognized :class:`Flavor`, or if the
            resolved integer index is out of range.
        """
        flavor_order = Flavor.ordered()
        flavor_values = [member.value for member in flavor_order]
        if isinstance(flavor, int):
            index = flavor
        else:
            if flavor.value not in flavor_values:
                raise ValueError(
                    f"Unsupported flavor {flavor!r}. Use one of {flavor_order}."
                )
            index = flavor_values.index(flavor.value)

        if index < 0 or index >= len(flavor_order):
            raise ValueError(f"Flavor index {index} is out of range.")
        return index

    def _selected_map(
        self, statistic: str, flavor: Flavor | int
    ) -> tuple[np.ndarray, Flavor]:
        """Return the 2D slice of ``statistic`` for the requested flavor.

        Parameters
        ----------
        statistic : str
            Statistic name; see :meth:`_statistic_map`.
        flavor : Flavor or int
            Flavor selector; see :meth:`_flavor_index`.

        Returns
        -------
        tuple[numpy.ndarray, Flavor]
            A ``(map2d, flavor)`` pair, where ``map2d`` has shape ``(ny, nx)``
            and ``flavor`` is the resolved :class:`Flavor` member.
        """
        flavor_order = Flavor.ordered()
        flavor_index = self._flavor_index(flavor)
        return self._statistic_map(statistic)[flavor_index], flavor_order[flavor_index]

    def lon_lat_grid(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Return 2D longitude and latitude grids in degrees.

        This method generates 2D grids of longitude and latitude coordinates that match
        the shape of the map. The grids can be constructed in three ways:

        1. If 1D longitude and latitude arrays are provided, they are converted to 2D grids
            using meshgrid. The 1D arrays must have lengths matching the map dimensions
            (nx and ny respectively).
        2. If 2D longitude and latitude arrays are provided, they are returned directly
            after validation that their shapes match the map shape.
        3. If no longitude/latitude arrays are provided, grids are generated based on the
            map extent and shape, creating evenly-spaced coordinate arrays.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            A tuple containing:
                - lon2d : np.ndarray
                    2D array of longitude values in degrees with shape (ny, nx)
                - lat2d : np.ndarray
                    2D array of latitude values in degrees with shape (ny, nx)

        Raises
        ------
        ValueError
             If 1D lon/lat arrays don't match map dimensions (nx, ny).
             If 2D lon/lat arrays don't match map shape.
             If lon and lat arrays have different dimensionalities (one 1D, one 2D).

        """
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

    def pixel_to_world(self, x: float, y: float) -> EarthLocation:
        """Convert zero-based pixel coordinates to an EarthLocation on Earth's surface.

        This method takes pixel coordinates from an image and converts them to geographic
        coordinates (latitude, longitude) using the internal longitude/latitude grid.
        The result is returned as an astropy EarthLocation object positioned at sea level.

        Parameters
        ----------
        x : float
            The zero-based x-coordinate (column) in pixels. Values outside the image bounds
            are clipped to the valid range [0, width-1].
        y : float
            The zero-based y-coordinate (row) in pixels. Values outside the image bounds
            are clipped to the valid range [0, height-1].

        Returns
        -------
        astropy.coordinates.EarthLocation
            The geographic coordinates corresponding to the pixel location, with height
            set to 0 meters (sea level).

        Raises
        ------
        ImportError
            If astropy.coordinates.EarthLocation or astropy.units is not available.

        Notes
        -----
        Pixel coordinates are rounded to the nearest integer and clipped to ensure they
        fall within the valid image bounds before lookup in the coordinate grid.

        """
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
        location_or_lon: EarthLocation | float,
        lat: float | None = None,
    ) -> tuple[int, int]:
        """
        Convert geographic coordinates to pixel indices in the map grid.

        This method converts either an EarthLocation object or longitude/latitude values
        to the corresponding pixel indices in the map's 2D grid. It finds the nearest grid
        point to the specified location using Euclidean distance.

        Parameters
        ----------
        location_or_lon : astropy.coordinates.EarthLocation or float
            Either an EarthLocation object containing the geographic coordinates,
            or the longitude value in degrees if `lat` is also provided.
        lat : float, optional
            The latitude value in degrees. Required if `location_or_lon` is a float.
            Ignored if `location_or_lon` is an EarthLocation object.

        Returns
        -------
        tuple[int, int]
            A tuple of (x_idx, y_idx) representing the pixel indices in the map grid
            that are closest to the specified location. x_idx corresponds to longitude
            and y_idx corresponds to latitude.

        Raises
        ------
        ValueError
            If `location_or_lon` is not an EarthLocation and `lat` is None.

        Notes
        -----
        The method uses the nearest-neighbor approach, finding the grid point with
        the minimum Euclidean distance to the specified coordinates.

        """
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

    def plot(
        self,
        flavor: Flavor | int = Flavor.U,
        ax: "plt.Axes | None" = None,
        add_colorbar: bool = True,
        color_by_region: bool = True,
        statistic: str = "median",
        log_scale: bool = True,
        draw_contours: bool = False,
        draw_regions: bool = True,
        contour_blur_sigma: float = 1.0,
    ) -> tuple["plt.Axes", "mpl.collections.QuadMesh"]:
        """
        Plot the geospatial dose-rate map and return the axes and mesh artist.

        Dose-rate values are displayed on a log10 scale by default. Region contours,
        coastlines, and gridlines are always drawn. When ``draw_contours=True``,
        contour lines are overlaid from the plotted map data. The axes use a
        cartopy ``PlateCarree`` projection.

        Parameters
        ----------
        flavor : Flavor or int, optional
            Which dosimeter flavor to plot. May be a :class:`Flavor` member or
            an integer index into :meth:`Flavor.ordered`. Default is
            ``Flavor.U``.
        ax : matplotlib.axes.Axes, optional
            Axes to draw into.  When ``None`` (default) a new figure and axes
            are created with a ``PlateCarree`` projection.
        add_colorbar : bool, optional
            Whether to add a colorbar to the figure.  Default is ``True``.
        color_by_region : bool, optional
            When ``True`` (default) map pixels are split into per-region arrays
            and each region is rendered with its own custom colormap (red for
            SAA, yellow for Polar Cap, blue for Outer Zone, green for Slot).
            A stacked set of horizontal colorbars is added, one per region.
            When ``False`` the full log10 map is plotted as a single
            ``pcolormesh`` using the ``viridis`` colormap and a single
            colorbar.
        statistic : str, optional
            Which statistic map to plot. One of ``"median"`` (default),
            ``"mean"``, ``"count"``, ``"min"``, ``"max"``, or ``"std"``.
            When ``"count"``, the color scale is linear regardless of
            ``log_scale``.
        log_scale : bool, optional
            When ``True`` (default) plot ``log10(map_data)`` (positive values
            only) with fixed range ``[-7, -2]``. When ``False`` plot linear
            ``map_data`` values and use matplotlib's default autoscaling.
            Ignored when ``statistic="count"``.
        draw_contours : bool, optional
            When ``True`` draw contour lines from the plotted map data on top of
            the filled mesh. Default is ``False``.
        draw_regions : bool, optional
            When ``True`` (default) label the region contours drawn by
            :func:`~swxsoc_reach.visualization.viz.plot_geomap`.
        contour_blur_sigma : float, optional
            Gaussian blur sigma (in pixels) applied to the map before contour
            extraction. Set to ``0`` to disable smoothing. Default is ``1.0``.

        Returns
        -------
        ax : matplotlib.axes.Axes
            The axes containing the plot.
        last_mesh : matplotlib.collections.QuadMesh
            The ``pcolormesh`` artist for the last drawn region (or the single
            mesh when ``color_by_region=False``).  Useful for further
            colorbar customisation by the caller.

        Notes
        -----
        - With ``log_scale=True`` the color scale is fixed to ``[-7, -2]`` in
          log10(rad/s).
        - The figure title is formatted as ``"{Time_start} - {Time_end} - {flavor_label}"``
          using the track time range and the selected flavor's label.
        - When ``color_by_region=True`` the per-region colorbars are placed
          below the map axes using absolute figure coordinates; callers
          adjusting the axes position after calling ``plot`` may need to
          reposition them.
        """

        data_unit = self[f"{statistic}_map"].unit
        _md, selected_flavor = self._selected_map(statistic, flavor)
        finite_values = _md[np.isfinite(_md)]
        is_count = statistic == "count"
        use_log_scale = log_scale and not is_count

        if is_count:
            colorbar_label = f"{data_unit}"
            contour_data = _md
            contour_levels = None
            if finite_values.size > 0:
                colorbarmin = float(np.nanmin(finite_values))
                colorbarmax = float(np.nanmax(finite_values))
            else:
                colorbarmin = 0.0
                colorbarmax = 0.0
        elif use_log_scale:
            colorbarmax = -2
            colorbarmin = -7
            colorbar_label = f"log ({data_unit})"
            contour_data = np.where(_md > 0, np.log10(_md), np.nan)
            # Plot contours only at 1e-6, 1e-5, 1e-4, 1e-3, 1e-2.
            contour_levels = np.array([-6, -5, -4, -3, -2], dtype=float)
        else:
            colorbarmax = None
            colorbarmin = None
            colorbar_label = f"{data_unit}"
            contour_data = _md
            contour_levels = None

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
        xylon, xylat = self.lon_lat_grid()

        region_mask = self["mask"].data

        if ax is None:
            fig = plt.figure(figsize=(11.69, 8.27))
            ax = plt.subplot(
                1,
                1,
                1,
                projection=ccrs.PlateCarree(central_longitude=0),
            )
        else:
            fig = ax.figure

        plot_geomap(
            ax=ax,
            draw_coastlines=True,
            draw_gridlines=True,
            draw_contours=False,
            label_contours=draw_regions,
        )

        if draw_contours:
            from scipy.ndimage import gaussian_filter

            def _smooth_for_contours(data: np.ndarray) -> np.ndarray:
                if contour_blur_sigma <= 0:
                    return data
                valid = np.isfinite(data)
                if not np.any(valid):
                    return data
                # Smooth data and validity mask separately so NaNs do not bleed
                # into surrounding regions during contour extraction.
                filled = np.where(valid, data, 0.0)
                weights = valid.astype(float)
                smooth_num = gaussian_filter(filled, sigma=contour_blur_sigma)
                smooth_den = gaussian_filter(weights, sigma=contour_blur_sigma)
                with np.errstate(invalid="ignore", divide="ignore"):
                    return np.where(smooth_den > 0, smooth_num / smooth_den, np.nan)

            finite_contours = contour_data[np.isfinite(contour_data)]
            if (
                log_scale
                and contour_levels is not None
                and finite_contours.size > 1
                and np.nanmin(finite_contours) < np.nanmax(finite_contours)
            ):
                # Draw contours at adaptive log-spaced levels
                smoothed = _smooth_for_contours(contour_data)
                contour_source = np.ma.masked_invalid(smoothed)
                ax.contour(
                    xylon,
                    xylat,
                    contour_source,
                    levels=contour_levels,
                    cmap="Reds",
                    linewidths=0.8,
                )
            elif (
                not log_scale
                and finite_contours.size > 1
                and np.nanmin(finite_contours) < np.nanmax(finite_contours)
            ):
                smoothed = _smooth_for_contours(contour_data)
                contour_source = np.ma.masked_invalid(smoothed)
                ax.contour(
                    xylon,
                    xylat,
                    contour_source,
                    cmap="Reds",
                    linewidths=0.8,
                )

        time_str = self.meta["Time_start"] + " - " + self.meta["Time_end"]
        ax.set_title(f"{time_str} - {selected_flavor.label}")

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
                if use_log_scale:
                    plot_data = np.where(region_data > 0, np.log10(region_data), np.nan)
                else:
                    plot_data = region_data
                mesh = ax.pcolormesh(
                    xylon,
                    xylat,
                    plot_data,
                    vmin=colorbarmin,
                    vmax=colorbarmax,
                    cmap=cmap,
                )
                meshes.append(mesh)

            if add_colorbar:
                if use_log_scale:
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
                    if use_log_scale and i < len(regions) - 1:
                        cbar.ax.set_xticklabels(tickemptylabels)
                    elif use_log_scale:
                        # Set colorbar ticks and labels at each order of magnitude
                        ticks = np.arange(colorbarmin, colorbarmax + 1)
                        cbar.set_ticks(ticks)
                        cbar.set_ticklabels([f"$10^{{{int(t)}}}$" for t in ticks])
                        cbar.set_label(colorbar_label, fontsize=10, labelpad=5)
                        cbar.ax.xaxis.set_label_position("bottom")
                        if draw_contours and contour_levels is not None:
                            contour_markers = contour_levels[
                                (contour_levels >= colorbarmin)
                                & (contour_levels <= colorbarmax)
                            ]
                            if contour_markers.size > 0:
                                cbar.ax.vlines(
                                    contour_markers,
                                    0.0,
                                    1.0,
                                    transform=cbar.ax.get_xaxis_transform(),
                                    colors="red",
                                    linewidth=1.0,
                                    alpha=0.9,
                                )
                    else:
                        cbar.set_label(colorbar_label, fontsize=10, labelpad=5)
                        cbar.ax.xaxis.set_label_position("bottom")
                    cbar_y -= cbar_height

            last_mesh = meshes[-1]
        else:
            plot_data = contour_data
            last_mesh = ax.pcolormesh(
                xylon,
                xylat,
                plot_data,
                vmin=colorbarmin,
                vmax=colorbarmax,
                cmap="viridis",
            )
            if add_colorbar:
                cbar = fig.colorbar(
                    last_mesh, ax=ax, label=colorbar_label, orientation="horizontal"
                )
                if use_log_scale:
                    ticks = np.arange(colorbarmin, colorbarmax + 1)
                    cbar.set_ticks(ticks)
                    cbar.set_ticklabels([f"$10^{{{int(t)}}}$" for t in ticks])
                    if draw_contours and contour_levels is not None:
                        contour_markers = contour_levels[
                            (contour_levels >= colorbarmin)
                            & (contour_levels <= colorbarmax)
                        ]
                        if contour_markers.size > 0:
                            cbar.ax.vlines(
                                contour_markers,
                                0.0,
                                1.0,
                                transform=cbar.ax.get_xaxis_transform(),
                                colors="red",
                                linewidth=1.0,
                                alpha=0.9,
                            )

        return ax, last_mesh

    def sum_per_region(self) -> dict[str, float]:
        """
        Return the sum of all map pixels within each region.

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
        _md = self.median_map[0]

        result: dict[str, float] = {}
        for region in Region.ordered():
            masked = np.where(region_mask[region.mask_index], _md, np.nan)
            result[region.key] = float(np.nansum(masked))
        return result

    @classmethod
    def load(cls, file_path: Path):
        """
        Load data from a file.

        Parameters
        ----------
        file_path : `pathlib.Path`
            A fully specified file path of the data file to load.

        Returns
        -------
        data : `SWXData`
            A `SWXData` object containing the loaded data.

        Raises
        ------
        ValueError: If the file type is not recognized as a file type that can be loaded.

        """
        from swxsoc.util.io import CDFHandler

        # Ensure file_path is a Path object
        file_path = Path(file_path)

        # Determine the file type
        file_extension = file_path.suffix

        # Create the appropriate handler object based on file type
        if file_extension == ".cdf":
            handler = CDFHandler()
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        # Use our Custom Schema
        schema = REACHDataSchema()
        # NOTE for GeoMap we want to override some Schema Requirements.
        # If this gets very ugly in the future we can consider a separate schema just for GeoMaps.
        # ===
        # We don't want to derive the resolution for the Epoch coordinate since it's not a regular time series, it's just a single timestamp representing the map time.
        schema.variable_attribute_schema["attribute_key"]["RESOLUTION"]["derived"] = (
            False
        )

        # Load data using the handler and return a REACHTrack object
        timeseries, support, spectra, meta = handler.load_data(file_path)
        return cls(
            timeseries=timeseries,
            support=support,
            spectra=spectra,
            meta=meta,
            schema=schema,
        )
