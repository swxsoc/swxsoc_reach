"""Generic geospatial map container with SunPy-like map helpers."""

from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.time import Time
from astropy.timeseries import TimeSeries
from scipy.stats import binned_statistic_2d
from swxsoc.swxdata import SWXData

from ..geomap import GenericGeoMap
from ..util.enums import Flavor, SensorId
from ..util.geom import load_region_contours, points_to_region_code
from ..visualization.viz import plot_region_code_contours_on_geomap


class REACHTrack(SWXData):
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
        file_path: str | Path,
    ):
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        trackdata = SWXData.load(file_path)
        super().__init__(
            timeseries=trackdata.timeseries,
            meta=trackdata.meta,
            support=trackdata.support,
            schema=trackdata.schema,
        )

    def sensor_id_to_index(self, sensor_id: SensorId | int) -> int:
        """Convert a SensorId or integer sensor number to the corresponding index."""
        if isinstance(sensor_id, int):
            sensor_id = SensorId(sensor_id)
        try:
            return np.where(self["sensor_ids"].data == sensor_id)[0][0]
        except IndexError:
            raise ValueError(
                f"Sensor ID {sensor_id} not found in track data."
            ) from None

    def get_track(self, reach_id: SensorId | int, dose_id: int) -> TimeSeries:
        if dose_id < 0 or dose_id >= self["observations"].data.shape[2]:
            raise ValueError(
                f"Invalid dose_id {dose_id}, must be between 0 and {self['observations'].shape[1] - 1}."
            )

        if isinstance(reach_id, int):
            sensor_id = SensorId.from_str(reach_id)

        reach_index = sensor_id.to_index()

        ts_times = Time(self["time"])
        ts = TimeSeries(time=ts_times)
        ts["dose"] = (
            self["observations"].data[:, reach_index, dose_id] * u.rad / u.second
        )
        ts["longitude"] = self["lon"].data[:, reach_index] * u.deg
        ts["latitude"] = self["lat"].data[:, reach_index] * u.deg
        ts["altitude"] = self["alt"].data[:, reach_index] * u.km
        # contour_paths = load_region_contours()
        # ts["region_code"] = points_to_region_code(
        #    lon=self["lon"].data[:, reach_index],
        #    lat=self["lat"].data[:, reach_index],
        #    paths_dict=contour_paths,
        # )
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

        valid = np.isfinite(lon_flat) & np.isfinite(lat_flat) & np.isfinite(obs_flat)
        statistic_data = binned_statistic_2d(
            lon_flat[valid],
            lat_flat[valid],
            obs_flat[valid],
            statistic=map_statistic,
            bins=[lon_edges, lat_edges],
        )
        m = statistic_data.statistic.T

        # Keep historical behavior for sum maps: empty bins are zero-valued.
        if map_statistic == "sum":
            m = np.nan_to_num(m, nan=0.0)

        plotTitlePre = str(
            np.min(time).strftime("%d %b %Y %H:%M")
            + " - "
            + np.max(time).strftime("%d %b %Y %H:%M")
        )

        return GenericGeoMap(
            data=m,
            timeseries=TimeSeries(time=[time[0], time[-1]]),
            mask=np.isnan(m),
            meta={
                "title": plotTitlePre,
                "coordinate_system": "geodetic",
                "extent": (-180.0, 180.0, -90.0, 90.0),
                "map_fields": {
                    "plotTitlePre": plotTitlePre,
                    "pltdos": "",
                },
            },
            unit="rad/s",
            lon=lon_bins,
            lat=lat_bins,
            flavor=flavor,
        )
