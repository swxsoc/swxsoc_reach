"""Generic geospatial map container with SunPy-like map helpers."""

import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from cartopy import crs as ccrs
from swxsoc.io.cdf_handler import CDFHandler
from swxsoc.swxdata import SWXData

from swxsoc_reach.util.enums import Flavor
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
    """
    A generic 2D geospatial map object.

    Provides a compact, SunPy-like API for geospatial dose-rate grids:
    per-statistic map accessors (``median_map``, ``mean_map``, ...),
    coordinate grid construction (``lon_lat_grid``), and an
    aggregated plotter (``plot``).

    The underlying storage is an :class:`swxsoc.swxdata.SWXData` container
    populated by :meth:`swxsoc_reach.track.trackbase.REACHTrack.to_geomap`.
    Each statistic map has shape ``(nflavors, ny, nx)``.
    """

    def __contains__(self, var_name: str) -> bool:
        """
        Return whether ``var_name`` exists in the underlying SWXData storage.

        ``SWXData`` only implements ``__getitem__``, so the default ``in``
        operator falls back to integer-index iteration (``self[0]``, ``self[1]``,
        ...) which raises ``KeyError``. Routing membership tests through
        ``__getitem__`` lets ``in`` resolve names across timeseries, support,
        and spectra without the caller specifying which.
        """
        try:
            self[var_name]
        except KeyError:
            return False
        return True

    @property
    def flavor_names(self) -> np.ndarray:
        if "dosimeter_flavor_names" not in self:
            return np.asarray([], dtype="U")
        return self["dosimeter_flavor_names"].data

    def map_data(self, statistic: str, flavor: Flavor) -> np.ndarray:
        """
        Return the map data for the specified statistic and flavor.

        Parameters
        ----------
        statistic : str
                    Statistic name. One of ``"median"``, ``"mean"``, ``"count"``,
                    ``"min"``, ``"max"``, or ``"std"``.
        flavor : Flavor

        Returns
        -------
        numpy.ndarray
            Array of shape ``(ny, nx)`` corresponding to the specified flavor.
        """
        # remove the first dimension (time)
        if f"{statistic}_map" not in self:
            raise ValueError(
                f"Statistic '{statistic}' is not available in this GenericGeoMap."
            )

        # Parse out the Statistic Map for each flavor
        # shape: (nflavors, lat, lon)
        all_flavor_data = self[f"{statistic}_map"].data[0]

        # Make sure the number of flavors in the metadata matches the number of slices in the statistic map
        if all_flavor_data.shape[0] != len(self.flavor_names):
            raise ValueError(
                "GeoMap flavor metadata does not match the data axis. "
                f"Metadata has {len(self.flavor_names)} flavors but "
                f"'{statistic}_map' stores {all_flavor_data.shape[0]} slices."
            )
        if flavor.name not in self.flavor_names:
            raise ValueError(
                f"Flavor '{flavor.name}' is not available in this GenericGeoMap."
            )
        else:
            flavor_index = np.where(self.flavor_names == flavor.name)[0][0]
        return all_flavor_data[flavor_index, :, :]

    @property
    def lon(self) -> np.ndarray:
        """Longitude coordinate array in degrees"""
        return self["lon"].data

    @property
    def lat(self) -> np.ndarray:
        """Latitude coordinate array in degrees"""
        return self["lat"].data

    @property
    def lon_lat_grid(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Return 2D longitude and latitude grids in degrees.

        This method generates 2D grids of longitude and latitude coordinates that match
        the shape of the map. The grids can be constructed in three ways:

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            A tuple containing:
                - lon2d : np.ndarray
                    2D array of longitude values in degrees with shape (ny, nx)
                - lat2d : np.ndarray
                    2D array of latitude values in degrees with shape (ny, nx)
        """
        lon2d, lat2d = np.meshgrid(self.lon, self.lat)
        return lon2d, lat2d

    @property
    def flavor(self) -> Flavor:
        """:class:`~swxsoc_reach.util.enums.Flavor` parsed from the ``Flavor`` metadata key."""
        return Flavor.from_str(self.meta.get("Flavor"))

    @property
    def shape(self) -> tuple[int, int]:
        """
        Map shape as ``(ny, nx)`` - spatial dimensions only.

        Returns the spatial dimensions of the map grid, regardless of whether
        time-indexed data is present in the underlying storage. If the internal
        data includes a time axis (e.g., ``(nt, ny, nx)``), only the spatial
        dimensions are returned.

        Returns
        -------
        tuple[int, int]
            The map dimensions as ``(num_latitude, num_longitude)``.
        """
        return self.map_data("median", Flavor.U).shape

    @property
    def coordinate_system(self) -> str:
        """
        Coordinate system label for this map.

        Returns the name of the coordinate system used by the map's longitude
        and latitude values. Typically ``"geodetic"`` for WGS84 coordinates.
        """
        return str(self.meta.get("coordinate_system", "geodetic"))

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """
        Map extent as lon/lat min-max values in degrees.

        Returns
        -------
        tuple[float, float, float, float]
            Extent as ``(lon_min, lon_max, lat_min, lat_max)`` in degrees.
        """
        return (
            float(self.lon.min()),
            float(self.lon.max()),
            float(self.lat.min()),
            float(self.lat.max()),
        )

    def plot(
        self,
        flavor: Flavor = Flavor.U,
        ax: "plt.Axes | None" = None,
        add_colorbar: bool = True,
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
        flavor : Flavor, optional
            Which dosimeter flavor to plot. Must be a :class:`Flavor` member.
            Default is ``Flavor.U``.
        ax : matplotlib.axes.Axes, optional
            Axes to draw into.  When ``None`` (default) a new figure and axes
            are created with a ``PlateCarree`` projection.
        add_colorbar : bool, optional
            Whether to add a colorbar to the figure.  Default is ``True``.
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
            The ``pcolormesh`` artist for the last drawn region.
            Useful for further colorbar customisation by the caller.

        Notes
        -----
        - With ``log_scale=True`` the color scale is fixed to ``[-7, -2]`` in
          log10(rad/s).
        - The figure title is formatted as
          ``"{Time_start} - {Time_end} - {flavor_label} {statistic} map"``
          using the track time range, the selected flavor's label, and the
          statistic name.
        """

        data_unit = self[f"{statistic}_map"].unit
        _md = self.map_data(statistic, flavor)
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

        xylon, xylat = self.lon_lat_grid

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
            draw_contours=draw_regions,
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
        ax.set_title(f"{time_str} - {flavor.label} {statistic} map")

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
