"""Generic geospatial map container with SunPy-like map helpers."""

import astropy.units as u
import numpy as np
from astropy.time import Time
from astropy.timeseries import TimeSeries
from astropy.nddata import NDData
from scipy.stats import binned_statistic_2d
from swxsoc.swxdata import SWXData

from swxsoc_reach.geomap import GenericGeoMap
from swxsoc_reach.util.enums import Flavor, Region, SensorId
from swxsoc_reach.util.geom import load_region_contours, points_to_region_code
from swxsoc_reach.util.schema import REACHDataSchema
from swxsoc_reach.visualization.viz import plot_region_code_contours_on_geomap


class REACHTrack(SWXData):
    """
    This is a container for REACH track data, which consists of time series of observations from multiple sensors as a function of time, longitude, and latitude.
    It provides methods for extracting individual tracks, plotting the track parameters as a function of time, plotting the track on a global geomap, and converting the track to a gridded geospatial map.
    """

    def get_track(self, reach_id: SensorId | int, dose_id: int) -> TimeSeries:
        """
        Retrieve a time series of tracking data for a specific sensor and dosimeter.

        Parameters
        ----------
        reach_id : SensorId or int
            Sensor selector. If a ``SensorId`` is provided, it must represent a
            single sensor. If an ``int`` is provided, it is interpreted as a
            zero-based sensor index (0-31), not a REACH numeric id.
        dose_id : int
            The dosimeter index. Must be between 0 and the number of dosimeter flavors minus 1.

        Returns
        -------
        TimeSeries
            A TimeSeries object containing:
            - dose : Dose rate in rad/s
            - longitude : Longitude coordinates in degrees
            - latitude : Latitude coordinates in degrees
            - altitude : Altitude values in km
            - region_code : Region codes determined from lon/lat coordinates
            - meta['dosimeter_id'] : The dosimeter flavor value for this track
            - meta['reach_id'] : The sensor identifier as string

        Raises
        ------
        ValueError
            If ``dose_id`` is out of range, if integer ``reach_id`` is outside
            0-31, or if ``reach_id`` does not resolve to a single valid sensor.
        """
        n_dosimeters = len(self["dosimeter_flavor_ids"].data)
        if dose_id < 0 or dose_id >= n_dosimeters:
            raise ValueError(
                f"Invalid dose_id {dose_id}, must be between 0 and {n_dosimeters - 1}."
            )

        if isinstance(reach_id, int):
            sensor_id = SensorId.from_str(reach_id)
        else:
            sensor_id = reach_id

        reach_index = sensor_id.to_index()

        # Get the Astropy Time for the TimeSeries
        ts_times = Time(self["time"])
        ts = TimeSeries(time=ts_times)

        # Get the Dose Rate Observational Data
        ts["dose"] = self["dose_rate"].data[:, reach_index, dose_id] * u.rad / u.second

        # Get Geodetic Coordinates and Region Codes
        ts["longitude"] = self["lon"].data[:, reach_index] * u.deg
        ts["latitude"] = self["lat"].data[:, reach_index] * u.deg
        ts["altitude"] = self["alt"].data[:, reach_index] * u.km

        # Define Region Codes based on lon/lat coordinates using the saved contour paths
        contour_paths = load_region_contours()
        ts["region_code"] = points_to_region_code(
            lon=self["lon"].data[:, reach_index],
            lat=self["lat"].data[:, reach_index],
            paths_dict=contour_paths,
        )

        # Update TimeSeries metadata
        self._unit = self["dose_rate"].unit
        ts.meta["dosimeter_id"] = self["dosimeter_flavors"].data[reach_index, dose_id]
        ts.meta["reach_id"] = str(sensor_id)

        return ts

    def plot(self, reach_id: SensorId | int, dose_id: int) -> None:
        """Plot track parameters as a function of time.

        Builds a vertically stacked set of subplots for all columns returned by
        :meth:`get_track` except ``time``. The ``dose`` series is plotted as
        ``log10(dose)`` and all other series are plotted in their native units.
        The figure title uses ``ts.meta['title']`` when present, otherwise it
        falls back to ``"{reach_id}, {dosimeter_id}"`` from track metadata.

        Parameters
        ----------
        reach_id : SensorId or int
            Sensor selector passed through to :meth:`get_track`.
        dose_id : int
            Dosimeter index passed through to :meth:`get_track`.

        Raises
        ------
        ValueError
            If no plottable track parameters are available.
            Any :class:`ValueError` raised by :meth:`get_track` may also
            propagate for invalid sensor or dosimeter selections.
        """
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        # Get Specific Track TimeSeries for the Given Sensor and Dosimeter
        ts = self.get_track(reach_id, dose_id)

        y_columns = [col for col in ts.colnames if col != "time"]
        if not y_columns:
            raise ValueError("No track parameters available to plot.")

        x_time = ts["time"].datetime

        # Setup Axes
        fig, axes = plt.subplots(
            nrows=len(y_columns),
            ncols=1,
            sharex=True,
            figsize=(10, max(3, 2.5 * len(y_columns))),
        )
        if len(y_columns) == 1:
            axes = [axes]

        # Plot Each Parameter
        for ax, col in zip(axes, y_columns):
            y_data = ts[col]
            if col == "dose":
                ax.plot(x_time, np.log10(y_data.value))
                unit = getattr(y_data, "unit", None)
                if unit is not None and str(unit):
                    label = f"Log10 Dose ({unit})"
                else:
                    label = "Log10 Dose"
            else:
                ax.plot(x_time, y_data)
                label = col.replace("_", " ").title()
                unit = getattr(y_data, "unit", None)
                if unit is not None and str(unit):
                    label = f"{label} ({unit})"
            ax.set_ylabel(label)

        axes[-1].set_xlabel("Time")
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        axes[0].set_title(
            ts.meta.get(
                "title",
                f"{ts.meta.get('reach_id')}, {ts.meta.get('dosimeter_id')}",
            )
        )
        fig.autofmt_xdate()
        fig.tight_layout()
        plt.show()

    def plotgeo(self, color_by: str = "dose") -> None:
        """Plot the track on a global geomap.

        Parameters
        ----------
        color_by : str, optional
            Scalar used to color track points. Supported values are
            ``"dose"`` and ``"region_code"``.
        """
        import matplotlib.pyplot as plt

        try:
            import cartopy.crs as ccrs
        except ImportError as exc:
            raise ImportError("plotgeo requires cartopy to be installed.") from exc

        lon = self["lon"].data
        lat = self["lat"].data

        # Verify Color Mapping and Prepare Color Values
        if color_by == "dose":
            values = np.asarray(np.log10(self["dose_rate"].data), dtype=float)
            colorbar_label = f"Dose ({self['dose_rate'].unit})"
            cmap = "viridis"
        elif color_by == "region_code":
            values = np.asarray(self.data["region_code"], dtype=float)
            colorbar_label = "Region Code"
            cmap = "tab10"
        else:
            raise ValueError(
                f"Unsupported color_by {color_by!r}. Use 'dose' or 'region_code'."
            )

        fig = plt.figure(figsize=(11, 6))
        ax = plt.axes(projection=ccrs.PlateCarree())
        plot_region_code_contours_on_geomap(
            ax=ax,
            draw_coastlines=True,
            draw_gridlines=True,
            label_contours=False,
        )

        # Draw line first, then points colored by selected scalar.
        ax.plot(
            lon,
            lat,
            color="black",
            linewidth=0.8,
            alpha=0.5,
            transform=ccrs.PlateCarree(),
        )
        # Plot points colored by the selected scalar
        scatter = ax.scatter(
            lon,
            lat,
            c=values,
            s=20,
            cmap=cmap,
            transform=ccrs.PlateCarree(),
        )

        fig.colorbar(scatter, ax=ax, label=colorbar_label, shrink=0.85)
        title = f"{self.reach_id} {self.dosimeter_id} {self.data.time[0].iso} to {self.data.time[-1].iso}"
        ax.set_title(self.meta.get("title", title))
        plt.show()

    def to_geomap(
        self,
        flavor: Flavor,
        lon_resolution: float = 1.0,
        lat_resolution: float = 1.0,
        map_statistic: str = "median",
    ) -> GenericGeoMap:
        """Convert track observations into a gridded geospatial map.

        The selected dosimeter ``flavor`` values are aggregated onto a regular
        geodetic longitude/latitude grid using a 2D binned statistic. Region
        masks are derived from saved contour paths and included in the output
        support variables.

        Parameters
        ----------
        flavor : Flavor
            Dosimeter flavor (or bitwise combination of flavors) to include in
            the map aggregation.
        lon_resolution : float, optional
            Longitude bin width in degrees. Default is 1.0.
        lat_resolution : float, optional
            Latitude bin width in degrees. Default is 1.0.
        map_statistic : str, optional
            Statistic passed to :func:`scipy.stats.binned_statistic_2d` for
            per-bin aggregation. Supported values are ``"sum"``, ``"mean"``,
            ``"median"``, ``"count"``, ``"min"``, ``"max"``, and ``"std"``.
            Default is ``"median"``.

        Returns
        -------
        GenericGeoMap
            A geospatial map object containing:

            - ``map_data``: gridded dose-rate statistic on ``(lat, lon)``
            - ``lon`` / ``lat``: grid-center coordinate vectors
            - ``mask``: boolean region masks with shape
              ``(nregions, nlat, nlon)``
            - metadata describing level, version, flavor, and coordinate system

        Raises
        ------
        ValueError
            If ``map_statistic`` is not one of the supported statistics, or if
            no data channels match the requested ``flavor``.
        """

        # Input Validation
        valid_statistics = {"sum", "mean", "median", "count", "min", "max", "std"}
        if map_statistic not in valid_statistics:
            raise ValueError(
                "map_statistic must be one of "
                f"{sorted(valid_statistics)}; got '{map_statistic}'."
            )

        # Mask ~= (32 sensors x 2 dosimeter flavors) to select only the flavors requested by the caller.
        flavor_mask = np.zeros(
            shape=(
                len(self["sensor_ids"].data),
                len(self["dosimeter_flavor_ids"].data),
            ),
            dtype=np.bool_,
        )

        # Populate Mask for each satellite and dosimeter flavor.
        for this_dosimeter in self["dosimeter_flavor_ids"].data:  # check each dosimeter
            for this_id in range(len(self["sensor_ids"].data)):  # check each sensor
                this_flavor = Flavor.from_str(
                    self["dosimeter_flavors"].data[this_id, this_dosimeter]
                )
                if this_flavor in flavor:
                    flavor_mask[this_id, this_dosimeter] = True
        if not np.any(flavor_mask):
            raise ValueError(f"Flavor {flavor} not found in data observation_flavors.")

        lat = self["lat"].data * u.deg
        lon = self["lon"].data * u.deg

        # Histogram bins are defined by edges, while the map stores center coordinates.
        lon_edges = np.arange(-180.0, 180.0 + lon_resolution, lon_resolution)
        lat_edges = np.arange(-90.0, 90.0 + lat_resolution, lat_resolution)
        lon_bins = 0.5 * (lon_edges[:-1] + lon_edges[1:])
        lat_bins = 0.5 * (lat_edges[:-1] + lat_edges[1:])

        # Apply Mask to get only the flavors requested by the caller
        flavor_data = (
            self["dose_rate"].data * flavor_mask[None, :, :]
        )  # [ntimes, nsats, ndos]

        lon_flat = lon.value.flatten()
        lat_flat = lat.value.flatten()
        obs_flat = flavor_data.sum(axis=2).flatten()

        ts = TimeSeries(time=[self.time[0]])
        ts.time.meta = {
            "CATDESC": "Observation Time",
            "VAR_TYPE": "support_data",
        }

        valid = np.isfinite(lon_flat) & np.isfinite(lat_flat) & np.isfinite(obs_flat)
        statistic_data = binned_statistic_2d(
            lon_flat[valid],
            lat_flat[valid],
            obs_flat[valid],
            statistic=map_statistic,
            bins=[lon_edges, lat_edges],
        )
        m = statistic_data.statistic.T

        # Build a region-code grid over the same lon/lat bins using the saved
        # contour paths, then derive per-region boolean masks.
        lon2d, lat2d = np.meshgrid(lon_bins, lat_bins)  # both shape (nlat, nlon)
        grid_points = np.column_stack([lon2d.ravel(), lat2d.ravel()])
        contour_paths = load_region_contours()
        region_codes_flat = np.zeros(len(grid_points), dtype=int)
        for code, path_obj in contour_paths.items():
            if path_obj is None:
                continue
            inside = path_obj.contains_points(grid_points)
            region_codes_flat[inside] = code
        region_code_grid = region_codes_flat.reshape(m.shape)

        # Stack into a single (nregions, nlat, nlon) boolean array using
        # canonical Region enum order.
        region_mask = np.stack(
            [
                np.isin(region_code_grid, region.signed_codes)
                for region in Region.ordered()
            ],
            axis=0,
        )

        # Define CDF Variables Dict.
        variables: dict[str, NDData] = {
            "map_data": NDData(
                # NOTE: Expand first dimension for 1 time step to conform to CDF Format requirements.
                data=np.expand_dims(m, axis=0),
                unit=u.rad / u.s,
                meta={
                    "CATDESC": f"{map_statistic} dose rate",
                    "VAR_TYPE": "data",
                    "UNITS": (u.rad / u.s).to_string(),
                    "DEPEND_0": "Epoch",
                    "DEPEND_1": "lat",
                    "DEPEND_2": "lon",
                    "LABL_PTR_1": "lat_label",
                    "LABL_PTR_2": "lon_label",
                },
            ),
            "lon": NDData(
                data=lon_bins,
                unit=u.deg,
                meta={
                    "CATDESC": "Longitude",
                    "VAR_TYPE": "support_data",
                    "UNITS": u.deg.to_string(),
                    "LABLAXIS": "Longitude Bins (degrees)",
                },
            ),
            "lat": NDData(
                data=lat_bins,
                unit=u.deg,
                meta={
                    "CATDESC": "Latitude",
                    "VAR_TYPE": "support_data",
                    "UNITS": u.deg.to_string(),
                    "LABLAXIS": "Latitude Bins (degrees)",
                },
            ),
            "lon_label": NDData(
                data=np.asarray(
                    [f"{lon_val:.2f} deg" for lon_val in lon_bins], dtype="U"
                ),
                meta={
                    "CATDESC": "Longitude bin labels",
                    "VAR_TYPE": "metadata",
                },
            ),
            "lat_label": NDData(
                data=np.asarray(
                    [f"{lat_val:.2f} deg" for lat_val in lat_bins], dtype="U"
                ),
                meta={
                    "CATDESC": "Latitude bin labels",
                    "VAR_TYPE": "metadata",
                },
            ),
            "regions": NDData(
                data=np.asarray(
                    [region.label for region in Region.ordered()], dtype="U"
                ),
                meta={
                    "CATDESC": "Region labels corresponding to mask axis-0",
                    "VAR_TYPE": "metadata",
                },
            ),
            "mask": NDData(
                data=region_mask,
                meta={
                    "CATDESC": (
                        "Boolean region masks, shape (nregions, nlat, nlon). "
                        "Axis-0 order: "
                        + ", ".join(
                            [
                                f"{region.mask_index}={region.label} (+/-{region.code})"
                                for region in Region.ordered()
                            ]
                        )
                    ),
                    "VAR_TYPE": "support_data",
                    "DEPEND_0": "regions",
                    "DEPEND_1": "lat",
                    "DEPEND_2": "lon",
                    "LABL_PTR_1": "regions",
                    "LABL_PTR_2": "lat_label",
                    "LABL_PTR_3": "lon_label",
                },
            ),
        }

        schema = REACHDataSchema()
        meta = dict(schema.default_global_attributes)

        # MAP Start/End Time Keywords
        meta["Time_start"] = self.time[0].isot
        meta["Time_end"] = self.time[-1].isot
        meta["Time_resolution"] = str((self.time[-1] - self.time[0]).sec * u.s)

        meta["Data_version"] = "1.0.0"
        meta["Data_level"] = "l2"
        meta["Instrument_mode"] = str(flavor)
        meta["Flavor"] = str(flavor)
        meta["coordinate_system"] = "geodetic"

        # NOTE for GeoMap we want to override some Schema Requirements.
        # If this gets very ugly in the future we can consider a separate schema just for GeoMaps.
        # ===
        # We don't want to derive the resolution for the Epoch coordinate since it's not a regular time series, it's just a single timestamp representing the map time.
        schema.variable_attribute_schema["attribute_key"]["RESOLUTION"]["derived"] = (
            False
        )

        return GenericGeoMap(
            timeseries=ts,
            support=variables,
            meta=meta,
            schema=schema,
        )
