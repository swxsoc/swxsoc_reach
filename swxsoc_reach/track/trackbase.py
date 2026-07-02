"""Generic geospatial map container with SunPy-like map helpers."""

import warnings
from copy import deepcopy
from pathlib import Path

import astropy.units as u
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import numpy as np
from astropy.nddata import NDData
from astropy.time import Time
from astropy.timeseries import TimeSeries
from scipy.stats import binned_statistic_2d
from swxsoc.io.cdf_handler import CDFHandler
from swxsoc.swxdata import SWXData

from swxsoc_reach import log
from swxsoc_reach.geomap import GenericGeoMap
from swxsoc_reach.util.enums import Flavor, SensorId
from swxsoc_reach.util.geom import load_region_contours, points_to_region_code
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


class REACHTrack(SWXData):
    """
    This is a container for REACH track data, which consists of time series of observations from multiple sensors as a function of time, longitude, and latitude.
    It provides methods for extracting individual tracks, plotting the track parameters as a function of time, plotting the track on a global geomap, and converting the track to a gridded geospatial map.
    """

    def get_track(self, reach_id: SensorId | int) -> TimeSeries:
        """
        Retrieve a time series of tracking data for a specific sensor.

        Parameters
        ----------
        reach_id : SensorId or int
            Sensor selector. If a ``SensorId`` is provided, it must represent a
            single sensor. If an ``int`` is provided, it is interpreted as a
            zero-based sensor index (0-31), not a REACH numeric id.

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
            If integer ``reach_id`` is outside 0-31, or if ``reach_id`` does
            not resolve to a single valid sensor.
        """
        if isinstance(reach_id, int):
            sensor_id = SensorId.from_str(reach_id)
        else:
            sensor_id = reach_id

        reach_index = sensor_id.to_index()

        # Get the Astropy Time for the TimeSeries
        ts_times = Time(self["time"])
        ts = TimeSeries(time=ts_times)

        flavor_str = []
        for dose_index in [0, 1]:
            # Get the Dose Rate Observational Data
            flavor_str.append(
                Flavor.from_str(self["dosimeter_flavors"].data[reach_index][dose_index])
            )
            ts[f"dose{dose_index}"] = (
                self["dose_rate"].data[:, reach_index, dose_index] * u.rad / u.second
            )

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
        ts.meta["flavors"] = flavor_str
        ts.meta["reach_id"] = str(sensor_id)

        return ts

    def truncate(self, start_time: Time, end_time: Time) -> "REACHTrack":
        """Return a new REACHTrack truncated to the specified time range.

        Creates a copy of the track data with all time-indexed arrays (dose rates,
        coordinates, quality flags, and sensor positions) sliced to include only
        observations between ``start_time`` and ``end_time`` (inclusive).

        Parameters
        ----------
        start_time : astropy.time.Time
            Start of time window (inclusive).
        end_time : astropy.time.Time
            End of time window (inclusive).

        Returns
        -------
        REACHTrack
            A new ``REACHTrack`` object containing the time-sliced data.

        Raises
        ------
        ValueError
            If no observations are found within the specified time range.
        """
        time_mask = (self.time >= start_time) & (self.time <= end_time)
        if not np.any(time_mask):
            raise ValueError(
                f"No observations found in the specified time range {start_time} to {end_time}."
            )
        default_key = self._default_timeseries_key
        truncated_timeseries = self._timeseries[default_key][time_mask]

        support_truncated = {}
        for this_key in self.data["support"].keys():
            support_truncated[this_key] = self.data["support"][this_key]

        for this_key in self.data["spectra"].keys():
            if len(self.data["spectra"][this_key].data.shape) == 2:
                data = self.data["spectra"][this_key].data[time_mask, :]
            elif len(self.data["spectra"][this_key].data.shape) == 3:
                data = self.data["spectra"][this_key].data[time_mask, :, :]
            else:
                raise ValueError(
                    f"Unexpected number of dimensions for spectra data: {self.data['spectra'][this_key].data.shape}"
                )
            these_data = NDData(
                data=data,
                meta=deepcopy(self.data["spectra"][this_key].meta),
            )
            support_truncated[this_key] = these_data

        return REACHTrack(
            timeseries=truncated_timeseries,
            support=support_truncated,
            meta=deepcopy(self.meta),
            schema=self.schema,
        )

    def plot(self, reach_id: SensorId | int) -> None:
        """Plot track parameters as a function of time.

        Builds a vertically stacked set of subplots for all columns returned by
        :meth:`get_track` except ``time``. The ``dose0`` and ``dose1`` series
        are plotted as ``log10(dose)`` and all other series are plotted in their
        native units. The figure title uses ``ts.meta['title']`` when present,
        otherwise it falls back to ``"{reach_id}"`` from track metadata.

        Parameters
        ----------
        reach_id : SensorId or int
            Sensor selector (0-31 or SensorId enum). Passed through to
            :meth:`get_track`.

        Raises
        ------
        ValueError
            If no plottable track parameters are available.
            Any :class:`ValueError` raised by :meth:`get_track` may also
            propagate for invalid sensor selection.
        """
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        # Get Specific Track TimeSeries for the Given Sensor and Dosimeter
        ts = self.get_track(reach_id)

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
            if col.count("dose"):
                ax.plot(x_time, np.log10(y_data.value))
                unit = getattr(y_data, "unit", None)
                if unit is not None and str(unit):
                    label = f"Log10 Dose ({unit}) - {ts.meta['flavors'][y_columns.index(col)]}"
                else:
                    label = f"Log10 Dose - {ts.meta['flavors'][y_columns.index(col)]}"
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
                f"{ts.meta.get('reach_id')}",
            )
        )
        fig.autofmt_xdate()
        fig.tight_layout()
        plt.show()

    def plotgeo(self, reach_id: SensorId | int, dose_index: int = 0) -> None:
        """Plot the track on a global geomap.

        Displays track observations as points and lines on a global map with
        region contour boundaries. Points are colored by the selected
        dosimeter's dose rate on a log10 scale.

        Parameters
        ----------
        reach_id : SensorId or int
            Sensor selector (0-31 or SensorId enum). Passed through to
            :meth:`get_track`.
        dose_index : int, optional
            Dosimeter index (0 or 1) selecting which dose-rate column
            (``dose0`` or ``dose1``) is used to color the points. Default is 0.

        Raises
        ------
        ValueError
            If dose_index is not 0 or 1, if no plottable track parameters are available,
        """
        # Get Specific Track TimeSeries for the Given Sensor and Dosimeter
        ts = self.get_track(reach_id=reach_id)
        lon = ts["longitude"]
        lat = ts["latitude"]
        cmap = "viridis"

        # Verify Color Mapping and Prepare Color Values
        if dose_index == 0:
            dose_data = ts["dose0"]
            values = np.log10(dose_data.value)
            colorbar_label = f"Dose0 (log10 {dose_data.unit})"
        elif dose_index == 1:
            dose_data = ts["dose1"]
            values = np.log10(dose_data.value)
            colorbar_label = f"Dose1 (log10 {dose_data.unit})"
        else:
            raise ValueError(f"Unsupported dose_index {dose_index!r}. Use 0 or 1.")

        fig = plt.figure(figsize=(11, 6))
        ax = plt.axes(projection=ccrs.PlateCarree())
        plot_geomap(
            ax=ax,
            draw_coastlines=True,
            draw_gridlines=True,
            label_contours=False,
        )

        # Draw line first, then points colored by selected scalar.
        ax.plot(
            lon.value,
            lat.value,
            color="black",
            linewidth=0.8,
            alpha=0.5,
            transform=ccrs.PlateCarree(),
        )
        # Plot points colored by the selected scalar
        scatter = ax.scatter(
            lon.value,
            lat.value,
            c=values,
            s=20,
            cmap=cmap,
            transform=ccrs.PlateCarree(),
        )

        fig.colorbar(scatter, ax=ax, label=colorbar_label, shrink=0.85)
        title = f"{ts.meta.get('reach_id')} {ts.meta.get('flavors')[dose_index]} {ts.time[0].iso} to {ts.time[-1].iso}"
        ax.set_title(ts.meta.get("title", title))
        plt.show()

    def to_geomap(
        self,
        lon_resolution: u.Quantity = 1.0 * u.deg,
        lat_resolution: u.Quantity = 1.0 * u.deg,
    ) -> GenericGeoMap:
        """
        Convert track observations into stacked geospatial maps.

        The track is aggregated for every individual flavor and for every
        supported statistic onto a regular geodetic longitude/latitude grid.
        The resulting map arrays are stored in support data as stacked arrays
        with shape ``(nflavors, nlat, nlon)``.

        Parameters
        ----------
        lon_resolution : `~astropy.units.Quantity`, optional
            Longitude bin width. Default is 1.0 deg.
        lat_resolution : `~astropy.units.Quantity`, optional
            Latitude bin width. Default is 1.0 deg.

        Returns
        -------
        GenericGeoMap
            A geospatial map object containing stacked per-flavor statistic
            arrays such as ``median_map``, ``mean_map``, and ``count_map``.
        """

        valid_statistics = ("sum", "mean", "median", "count", "min", "max", "std")

        nsensors = len(self["sensor_ids"].data)
        ndos = len(self["dosimeter_flavor_ids"].data)

        dosimeter_flavor_grid = np.empty((nsensors, ndos), dtype=object)
        for this_dosimeter in self["dosimeter_flavor_ids"].data:
            for this_id in range(nsensors):
                dosimeter_flavor_grid[this_id, this_dosimeter] = Flavor.from_str(
                    self["dosimeter_flavors"].data[this_id, this_dosimeter]
                )

        lat = self["lat"].data * u.deg
        lon = self["lon"].data * u.deg

        # Histogram bins are defined by edges, while the map stores center coordinates.
        lon_resolution_deg = lon_resolution.to(u.deg).value
        lat_resolution_deg = lat_resolution.to(u.deg).value
        lon_edges = np.arange(
            -180.0, 180.0 + lon_resolution_deg, lon_resolution_deg, dtype=np.float16
        )
        lat_edges = np.arange(
            -90.0, 90.0 + lat_resolution_deg, lat_resolution_deg, dtype=np.float16
        )
        lon_bins = 0.5 * (lon_edges[:-1] + lon_edges[1:])
        lat_bins = 0.5 * (lat_edges[:-1] + lat_edges[1:])

        lon_flat = lon.value.flatten()
        lat_flat = lat.value.flatten()

        ts = TimeSeries(time=[self.time[0]])
        ts.time.meta = {
            "CATDESC": "Observation Time",
            "VAR_TYPE": "support_data",
        }

        lon2d, lat2d = np.meshgrid(lon_bins, lat_bins)
        grid_shape = lon2d.shape

        # Stub out a dictionary to hold lists of per-flavor statistic maps, which we will stack at the end.
        statistic_maps: dict[str, list[np.ndarray]] = {
            statistic: [] for statistic in valid_statistics
        }

        # Loop over all flavors in canonical order and compute the statistics for each flavor, then append to the corresponding list in statistic_maps.
        ordered_flavors = Flavor.ordered()
        for flavor in ordered_flavors:
            flavor_mask = dosimeter_flavor_grid == flavor

            # Skip if no observations for this flavor
            if not np.any(flavor_mask):
                log.warning(
                    f"No observations found for flavor {flavor.name}. Filling with empty maps."
                )
                for statistic in valid_statistics:
                    if statistic == "count":
                        statistic_maps[statistic].append(np.zeros(grid_shape))
                    else:
                        statistic_maps[statistic].append(np.full(grid_shape, np.nan))
                continue

            # Slice out the dose_rate data for this flavor
            flavor_data = np.where(
                flavor_mask[None, :, :],
                self["dose_rate"].data,
                np.nan,
            )
            # Sum over the dosimeter axis to combine multiple dosimeters of the same flavor, then flatten for binning.
            obs = np.nansum(flavor_data, axis=2)
            has_selected_observation = np.any(np.isfinite(flavor_data), axis=2)
            obs[~has_selected_observation] = np.nan
            obs_flat = obs.flatten()
            valid = (
                np.isfinite(lon_flat) & np.isfinite(lat_flat) & np.isfinite(obs_flat)
            )

            # If there are valid, finite observations for this flavor, compute statistics and append to maps.
            if np.any(valid):
                for statistic in valid_statistics:
                    statistic_data = binned_statistic_2d(
                        lon_flat[valid],
                        lat_flat[valid],
                        obs_flat[valid],
                        statistic=statistic,
                        bins=[lon_edges, lat_edges],
                    )
                    statistic_maps[statistic].append(statistic_data.statistic.T)
            # If there are no valid observations for this flavor, populate empty maps with NaNs (or zeros for count)
            else:
                # No valid samples for this flavor; populate empty maps.
                for statistic in valid_statistics:
                    if statistic == "count":
                        statistic_maps[statistic].append(np.zeros(grid_shape))
                    else:
                        statistic_maps[statistic].append(np.full(grid_shape, np.nan))

        dosimeter_flavor_names = np.asarray(
            [flavor.name for flavor in ordered_flavors], dtype="U"
        )
        dosimeter_flavor_ids = np.array(
            [i for i in range(len(ordered_flavors))], dtype=int
        )
        dosimeter_flavor_labels = np.asarray(
            [flavor.label for flavor in ordered_flavors], dtype="U"
        )

        # Define CDF Variables Dict.
        variables: dict[str, NDData] = {
            "dosimeter_flavor_names": NDData(
                data=dosimeter_flavor_names,
                meta={
                    "CATDESC": "Human-Readable Names for dosimeter flavors dimension",
                    "VAR_TYPE": "metadata",
                },
            ),
            "dosimeter_flavor_ids": NDData(
                data=dosimeter_flavor_ids,
                meta={
                    "CATDESC": "ID for dosimeter flavors dimension",
                    "VAR_TYPE": "metadata",
                },
            ),
            "dosimeter_flavor_labels": NDData(
                data=dosimeter_flavor_labels,
                meta={
                    "CATDESC": "Label for dosimeter flavors dimension",
                    "VAR_TYPE": "metadata",
                },
            ),
            "statistics": NDData(
                data=np.asarray(list(valid_statistics), dtype="U"),
                meta={
                    "CATDESC": "Supported statistics for geospatial maps",
                    "VAR_TYPE": "metadata",
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
        }

        for statistic in valid_statistics:
            if len(statistic_maps[statistic]) != len(ordered_flavors):
                raise ValueError(
                    f"Statistic '{statistic}' has {len(statistic_maps[statistic])} flavor slices, "
                    f"expected {len(ordered_flavors)}."
                )
            unit = u.count if statistic == "count" else u.rad / u.s
            flavor_maps = np.stack(statistic_maps[statistic], axis=0, dtype=np.float32)
            variables[f"{statistic}_map"] = NDData(
                # NOTE: Expand first dimension for 1 time step to conform to CDF Format requirements.
                data=np.expand_dims(flavor_maps, axis=0),
                unit=unit,
                meta={
                    "CATDESC": f"{statistic} dose rate",
                    "VAR_TYPE": "data",
                    "UNITS": unit.to_string(),
                    "DEPEND_0": "Epoch",
                    "DEPEND_1": "dosimeter_flavor_ids",
                    "DEPEND_2": "lat",
                    "DEPEND_3": "lon",
                    "LABL_PTR_1": "dosimeter_flavor_labels",
                    "LABL_PTR_2": "lat_label",
                    "LABL_PTR_3": "lon_label",
                },
            )

        schema = REACHDataSchema()
        meta = dict(schema.default_global_attributes)

        # MAP Start/End Time Keywords
        meta["Time_start"] = self.time[0].isot
        meta["Time_end"] = self.time[-1].isot
        meta["Time_resolution"] = str((self.time[-1] - self.time[0]).sec * u.s)

        meta["Data_version"] = "1.0.0"
        meta["Data_level"] = "l2"
        meta["Instrument_mode"] = str(
            Flavor.ALL
        )  # TODO: Should not be hardcoded; should be derived from the data.
        meta["Flavor"] = str(
            Flavor.ALL.name
        )  # TODO: Should not be hardcoded; should be derived from the data.
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

        # Load data using the handler and return a REACHTrack object
        timeseries, support, spectra, meta = handler.load_data(file_path)
        return cls(
            timeseries=timeseries,
            support=support,
            spectra=spectra,
            meta=meta,
            schema=schema,
        )
