"""Generic geospatial map container with SunPy-like map helpers."""

from os import times
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.time import Time
from astropy.timeseries import TimeSeries
from scipy.stats import binned_statistic_2d
from swxsoc.swxdata import SWXData

from swxsoc_reach.util.schema import REACHDataSchema

from ..geomap import GenericGeoMap
from ..util.enums import Flavor, Region, SensorId
from ..util.geom import load_region_contours, points_to_region_code
from ..visualization.viz import plot_region_code_contours_on_geomap


class REACHTrack(SWXData):
    """
    This is a container for REACH track data, which consists of time series of observations from multiple sensors as a function of time, longitude, and latitude. It provides methods for extracting individual tracks, plotting the track parameters as a function of time, plotting the track on a global geomap, and converting the track to a gridded geospatial map.
    """

    def truncate(self, time_start: Time, time_end: Time) -> "REACHTrack":
        """Return a new REACHTrack truncated to the specified time range."""
        mask = (self["time"] >= time_start) & (self["time"] <= time_end)
        raise NotImplementedError("Truncation not yet implemented for REACHTrack.")

    def get_track(self, reach_id: SensorId | int, dose_id: int) -> TimeSeries:
        if dose_id < 0 or dose_id >= self["observations"].data.shape[2]:
            raise ValueError(
                f"Invalid dose_id {dose_id}, must be between 0 and {self['observations'].shape[1] - 1}."
            )

        if isinstance(reach_id, int):
            sensor_id = SensorId.from_str(reach_id)
        else:
            sensor_id = reach_id

        reach_index = sensor_id.to_index()

        ts_times = Time(self["time"])
        ts = TimeSeries(time=ts_times)
        ts["dose"] = (
            self["observations"].data[:, reach_index, dose_id] * u.rad / u.second
        )
        ts["longitude"] = self["lon"].data[:, reach_index] * u.deg
        ts["latitude"] = self["lat"].data[:, reach_index] * u.deg
        ts["altitude"] = self["alt"].data[:, reach_index] * u.km
        contour_paths = load_region_contours()
        ts["region_code"] = points_to_region_code(
            lon=self["lon"].data[:, reach_index],
            lat=self["lat"].data[:, reach_index],
            paths_dict=contour_paths,
        )
        self._unit = self["observations"].unit
        ts.meta["dosimeter_id"] = self["observation_flavors"].data[reach_index, dose_id]
        ts.meta["reach_id"] = str(sensor_id)
        return ts

    def plot(self, reach_id: SensorId | int, dose_id: int) -> None:
        """Plot all track parameters as a function of time."""
        ts = self.get_track(reach_id, dose_id)
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        y_columns = [col for col in ts.colnames if col != "time"]
        if not y_columns:
            raise ValueError("No track parameters available to plot.")

        x_time = ts["time"].datetime

        fig, axes = plt.subplots(
            nrows=len(y_columns),
            ncols=1,
            sharex=True,
            figsize=(10, max(3, 2.5 * len(y_columns))),
        )
        if len(y_columns) == 1:
            axes = [axes]

        for ax, col in zip(axes, y_columns):
            y_data = ts[col]
            if col == "dose":
                ax.plot(x_time, np.log10(y_data.value))
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

        lon_data = self.data["longitude"]
        lat_data = self.data["latitude"]
        lon = np.asarray(getattr(lon_data, "value", lon_data), dtype=float)
        lat = np.asarray(getattr(lat_data, "value", lat_data), dtype=float)

        if color_by == "dose":
            values = np.asarray(np.log10(self.data["dose"].value), dtype=float)
            colorbar_label = f"Dose ({self.unit})"
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
        """Convert this track to a geospatial map object."""

        valid_statistics = {"sum", "mean", "median", "count", "min", "max", "std"}
        if map_statistic not in valid_statistics:
            raise ValueError(
                "map_statistic must be one of "
                f"{sorted(valid_statistics)}; got '{map_statistic}'."
            )

        flavor_mask = np.zeros(shape=(32, 2), dtype=np.bool_)

        for this_dosimeter in [0, 1]:  # check each dosimeter
            for this_id in np.arange(32):
                this_flavor = Flavor.from_str(
                    self["observation_flavors"].data[this_id, this_dosimeter]
                )
                if this_flavor in flavor:
                    flavor_mask[this_id, this_dosimeter] = True
        if not np.any(flavor_mask):
            raise ValueError(f"Flavor {flavor} not found in data observation_flavors.")

        lat = self["lat"].data * u.deg
        lon = self["lon"].data * u.deg
        time = self["time"]

        # Histogram bins are defined by edges, while the map stores center coordinates.
        lon_edges = np.arange(-180.0, 180.0 + lon_resolution, lon_resolution)
        lat_edges = np.arange(-90.0, 90.0 + lat_resolution, lat_resolution)
        lon_bins = 0.5 * (lon_edges[:-1] + lon_edges[1:])
        lat_bins = 0.5 * (lat_edges[:-1] + lat_edges[1:])

        flavor_data = (
            self["observations"].data * flavor_mask[None, :, :]
        )  # [ntimes, nsats, ndos]

        lon_flat = lon.value.flatten()
        lat_flat = lat.value.flatten()
        obs_flat = flavor_data.sum(axis=2).flatten()

        ts = TimeSeries(time=[self.time[0], self.time[-1]])
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

        from astropy.nddata import NDData

        variables: dict[str, NDData] = {
            "map_data": NDData(
                data=m,
                unit=u.rad / u.s,
                mask=np.isnan(m),
                meta={
                    "CATDESC": "Mean dose rate",
                    "VAR_TYPE": "support_data",
                    "UNITS": (u.rad / u.s).to_string(),
                    "DEPEND_0": "Epoch",
                    "DEPEND_2": "lon, lat",
                    "LABL_PTR_1": "Epoch_label",
                    "LABL_PTR_2": "lon, lat",
                },
            ),
            "lon": NDData(
                data=lon_bins,
                unit=u.deg,
                meta={
                    "CATDESC": "Longitude",
                    "VAR_TYPE": "support_data",
                    "UNITS": u.deg.to_string(),
                    "DEPEND_0": "Epoch",
                    "LABL_PTR_1": "Epoch_label",
                },
            ),
            "lat": NDData(
                data=lat_bins,
                unit=u.deg,
                meta={
                    "CATDESC": "Latitude",
                    "VAR_TYPE": "support_data",
                    "UNITS": u.deg.to_string(),
                    "DEPEND_0": "Epoch",
                },
            ),
            "Epoch_label": NDData(
                data=np.array([t.isot for t in ts.time]),
                meta={"CATDESC": "Label for Epoch dimension", "VAR_TYPE": "metadata"},
            ),
            "mask": NDData(
                data=region_mask,
                meta={
                    "CATDESC": (
                        "Boolean region masks, shape (nregions, nlat, nlon). "
                        "Axis-0 order: "
                        + ", ".join(
                            [
                                f"{region.mask_index}={region.label} (±{region.code})"
                                for region in Region.ordered()
                            ]
                        )
                    ),
                    "VAR_TYPE": "support_data",
                },
            ),
        }

        schema = REACHDataSchema()
        meta = dict(schema.default_global_attributes)
        meta["Data_version"] = "1.0.0"
        meta["Data_level"] = "l2"
        meta["Flavor"] = str(flavor)
        meta["coordinate_system"] = "geodetic"

        return GenericGeoMap(
            timeseries=ts,
            support=variables,
            meta=meta,
            schema=self.schema,
        )
