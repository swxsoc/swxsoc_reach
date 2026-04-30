"""Generic geospatial map container with SunPy-like map helpers."""

import astropy.units as u
import numpy as np
from astropy.time import Time
from astropy.timeseries import TimeSeries
from swxsoc.swxdata import SWXData

from ..util.util import compute_region_code
from ..visualization.viz import plot_region_code_contours_on_geomap


class REACHTrack(object):
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
        trackdata: SWXData,
        reach_id: int,
        dose_id: int,
    ):
        ts_times = Time(trackdata["time"])
        ts = TimeSeries(time=ts_times)
        ts["dose"] = (
            trackdata["observations"].data[:, dose_id, reach_id] * u.rad / u.second
        )
        ts["longitude"] = trackdata["lon"].data[:, reach_id] * u.deg
        ts["latitude"] = trackdata["lat"].data[:, reach_id] * u.deg
        ts["altitude"] = trackdata["alt"].data[:, reach_id] * u.km
        ts["region_code"] = compute_region_code(
            lon=trackdata["lon"].data[:, reach_id],
            lat=trackdata["lat"].data[:, reach_id],
        )
        self._data = ts
        self._meta = trackdata.meta
        self._unit = trackdata["observations"].unit
        self.dosimeter_id = trackdata["observation_flavors"].data[reach_id, dose_id]
        self.reach_id = trackdata["sensor_ids"].data[reach_id]

    def __repr__(self):
        result = f"<REACHTrack reach_id={self.reach_id} dosimeter_id={self.dosimeter_id} time_range={self.data.time[0]} to {self.data.time[-1]}>"
        return result

    @property
    def data(self) -> np.ma.MaskedArray:
        """Map data as a masked 2D array."""
        return self._data

    @property
    def meta(self) -> dict[str, str]:
        """Map metadata dictionary."""
        return self._meta

    @property
    def unit(self) -> str | None:
        """Unit label for map values."""
        return self._unit

    def __getitem__(self, key):
        """Return a time-sliced subtrack via ``track[start:end]`` syntax."""
        if isinstance(key, slice):
            if key.step not in (None, 1):
                raise ValueError("Slice step is not supported for REACHTrack.")
            return self.subtrack(start=key.start, end=key.stop)
        raise TypeError(
            "REACHTrack only supports slicing by time interval, e.g. "
            "track['2026-01-01T00:00:00':'2026-01-01T01:00:00']"
        )

    def subtrack(self, start: str | Time | None = None, end: str | Time | None = None):
        """Return a new track constrained to a smaller time interval.

        Parameters
        ----------
        start : str or astropy.time.Time, optional
            Inclusive start time. Uses the first timestamp when omitted.
        end : str or astropy.time.Time, optional
            Inclusive end time. Uses the last timestamp when omitted.

        Returns
        -------
        REACHTrack
            New ``REACHTrack`` instance containing only samples within
            ``[start, end]``.

        Raises
        ------
        ValueError
            If ``end`` is earlier than ``start`` or no samples are found.
        """
        start_time = self.data.time[0] if start is None else Time(start)
        end_time = self.data.time[-1] if end is None else Time(end)

        if end_time < start_time:
            raise ValueError("end must be greater than or equal to start.")

        mask = (self.data.time >= start_time) & (self.data.time <= end_time)
        if not np.any(mask):
            raise ValueError("No track samples found in the requested time interval.")

        new_track = object.__new__(REACHTrack)
        new_track._data = self.data[mask]
        new_track._meta = dict(self.meta)
        new_track._unit = self.unit
        new_track.dosimeter_id = self.dosimeter_id
        new_track.reach_id = self.reach_id
        return new_track

    def plot(self) -> None:
        """Plot all track parameters as a function of time."""
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        y_columns = [col for col in self.data.colnames if col != "time"]
        if not y_columns:
            raise ValueError("No track parameters available to plot.")

        x_time = self.data.time.datetime

        fig, axes = plt.subplots(
            nrows=len(y_columns),
            ncols=1,
            sharex=True,
            figsize=(10, max(3, 2.5 * len(y_columns))),
        )
        if len(y_columns) == 1:
            axes = [axes]

        for ax, col in zip(axes, y_columns):
            y_data = self.data[col]
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
            self.meta.get("title", f"{self.reach_id} {self.dosimeter_id}")
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
