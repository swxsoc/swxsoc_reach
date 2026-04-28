"""Generic geospatial map container with SunPy-like map helpers."""

from __future__ import annotations

from curses.ascii import alt
from typing import Any

import astropy.units as u
import numpy as np
from astropy.coordinates import EarthLocation
from swxsoc.swxdata import SWXData

from ..util.flavors import Flavor


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
        meta: dict[str, Any] | None = None,
        *,
        mask: np.ndarray | None = None,
        unit: str | None = None,
        lon: np.ndarray | None = None,
        lat: np.ndarray | None = None,
    ) -> None:
        arr = np.asarray(data)
        if arr.ndim != 2:
            raise ValueError(
                f"GenericGeoMap expects 2D data, got array with shape {arr.shape}."
            )

        self._data = np.ma.array(arr, mask=mask, copy=True)
        self._meta = dict(meta) if meta is not None else {}
        self._unit = unit
        self.plot_settings = {
            "cmap": self._meta.get("cmap", "viridis"),
            "origin": self._meta.get("origin", "lower"),
        }

        self._lon = None if lon is None else np.asarray(lon, dtype=float)
        self._lat = None if lat is None else np.asarray(lat, dtype=float)
        self._validate_coordinates()

    def __repr__(self) -> str:
        title = self._meta.get("title", "Untitled")
        coord_sys = self.coordinate_system
        return (
            f"GenericGeoMap(title={title!r}, shape={self.shape}, "
            f"coordinate_system={coord_sys!r}, unit={self.unit!r})"
        )

    @property
    def data(self) -> np.ma.MaskedArray:
        """Map data as a masked 2D array."""
        return self._data

    @property
    def meta(self) -> dict[str, Any]:
        """Map metadata dictionary."""
        return self._meta

    @property
    def unit(self) -> str | None:
        """Unit label for map values."""
        return self._unit

    @property
    def quantity(self):
        """Data as an astropy Quantity when astropy is available."""
        if self._unit is None or u is None:
            return self._data
        return np.asarray(self._data) * u.Unit(self._unit)

    @property
    def shape(self) -> tuple[int, int]:
        """Map shape as ``(ny, nx)``."""
        return self._data.shape

    @property
    def dimensions(self) -> tuple[int, int]:
        """Alias for shape, kept for SunPy-style familiarity."""
        return self.shape

    @property
    def coordinate_system(self) -> str:
        """Coordinate system label for this map."""
        return str(self._meta.get("coordinate_system", "geodetic"))

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """Map extent as lon/lat min-max values in degrees."""
        if "extent" in self._meta:
            lon_min, lon_max, lat_min, lat_max = self._meta["extent"]
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
        return GenericGeoMap(
            np.asarray(self._data),
            dict(self._meta),
            mask=np.ma.getmaskarray(self._data),
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
        if "extent" in self._meta:
            lon_min, lon_max, lat_min, lat_max = self._meta["extent"]
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

        sub_data = self._data[y0:y1, x0:x1]
        sub_lon = lon2d[y0:y1, x0:x1]
        sub_lat = lat2d[y0:y1, x0:x1]
        sub_meta = dict(self._meta)
        sub_meta["extent"] = (
            float(np.nanmin(sub_lon)),
            float(np.nanmax(sub_lon)),
            float(np.nanmin(sub_lat)),
            float(np.nanmax(sub_lat)),
        )
        return GenericGeoMap(
            np.asarray(sub_data),
            meta=sub_meta,
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

        data_resampled = self._data[np.ix_(y_index, x_index)]
        lon2d, lat2d = self.lon_lat_grid()
        lon_resampled = lon2d[np.ix_(y_index, x_index)]
        lat_resampled = lat2d[np.ix_(y_index, x_index)]

        resampled_meta = dict(self._meta)
        resampled_meta["extent"] = (
            float(np.nanmin(lon_resampled)),
            float(np.nanmax(lon_resampled)),
            float(np.nanmin(lat_resampled)),
            float(np.nanmax(lat_resampled)),
        )

        return GenericGeoMap(
            np.asarray(data_resampled),
            meta=resampled_meta,
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
        wrapped_data = self._data[:, column_order]
        wrapped_lon = wrapped_lon[:, column_order]
        wrapped_lat = lat2d[:, column_order]

        wrapped_meta = dict(self._meta)
        wrapped_meta["extent"] = (
            float(np.nanmin(wrapped_lon)),
            float(np.nanmax(wrapped_lon)),
            float(np.nanmin(wrapped_lat)),
            float(np.nanmax(wrapped_lat)),
        )

        return GenericGeoMap(
            np.asarray(wrapped_data),
            meta=wrapped_meta,
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
        flav: str | None = None,
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

        # If REACH region map fields are present, use the same layered
        # geospatial rendering style used by visualization.plot_mapdata.
        region_keys = {"xylon", "xylat", "SAA", "PC", "outrad", "slot"}
        map_fields = self._meta.get("map_fields", self._meta)
        if isinstance(map_fields, dict) and region_keys.issubset(map_fields.keys()):
            colorbarmax = -2
            colorbarmin = -7

            cdi = "#093145"
            cda = "#107896"
            cla = "#43abc9"
            cdk = "#829356"
            clk = "#b5c689"
            cdd = "#bca136"
            cld = "#efd469"
            cdr = "#9a2617"
            clr = "#cd594a"
            clg = "#F3F4F6"

            greencolors = [clg, clk, cdk]
            yellowcolors = [clg, cld, cdd]
            redcolors = [clg, clr, cdr]
            bluecolors = [clg, cla, cda, cdi]

            bluemap = mpl.colors.LinearSegmentedColormap.from_list("", bluecolors)
            greenmap = mpl.colors.LinearSegmentedColormap.from_list("", greencolors)
            yellowmap = mpl.colors.LinearSegmentedColormap.from_list("", yellowcolors)
            redmap = mpl.colors.LinearSegmentedColormap.from_list("", redcolors)

            xylon = np.asarray(map_fields["xylon"])
            xylat = np.asarray(map_fields["xylat"])
            SAA = np.asarray(map_fields["SAA"])
            PC = np.asarray(map_fields["PC"])
            outrad = np.asarray(map_fields["outrad"])
            slot = np.asarray(map_fields["slot"])

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
                ax.coastlines()
                ax.gridlines(
                    draw_labels=True,
                    xlocs=np.arange(-180, 180, 30),
                    ylocs=np.arange(-90, 90, 10),
                    color="gray",
                    linestyle="--",
                )

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

            title_pre = str(map_fields.get("plotTitlePre", self._meta.get("title", "")))
            this_flav = str(flav or self._meta.get("flav", ""))
            pltdos = str(map_fields.get("pltdos", ""))

            try:
                pltname = " " + Flavor.from_str(this_flav).label
            except ValueError:
                pltname = f"{this_flav} {pltdos}".strip()

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
                cbarPC.set_label("log (rads/sec)", fontsize=10, labelpad=5)
                cbarPC.ax.xaxis.set_label_position("bottom")

            return ax, mapPC

        if ax is None:
            if has_cartopy:
                fig, ax = plt.subplots(subplot_kw={"projection": ccrs.PlateCarree()})
            else:
                fig, ax = plt.subplots()
        else:
            fig = ax.figure

        plot_kwargs = dict(self.plot_settings)
        plot_kwargs.update(kwargs)

        if use_world_coordinates:
            lon2d, lat2d = self.lon_lat_grid()
            if has_cartopy:
                artist = ax.pcolormesh(
                    lon2d,
                    lat2d,
                    self._data,
                    shading="auto",
                    transform=ccrs.PlateCarree(),
                    cmap=plot_kwargs.get("cmap", "viridis"),
                )
                ax.coastlines()
                ax.gridlines(draw_labels=True)
            else:
                artist = ax.pcolormesh(
                    lon2d,
                    lat2d,
                    self._data,
                    shading="auto",
                    cmap=plot_kwargs.get("cmap", "viridis"),
                )
                ax.set_xlabel("Longitude [deg]")
                ax.set_ylabel("Latitude [deg]")
        else:
            artist = ax.imshow(self._data, **plot_kwargs)
            ax.set_xlabel("X Pixel")
            ax.set_ylabel("Y Pixel")

        ax.set_title(self._meta.get("title", "Geo Map"))
        if add_colorbar:
            label = self._unit or self._meta.get("colorbar_label", "")
            fig.colorbar(artist, ax=ax, label=label)

        return ax, artist

    def _validate_coordinates(self) -> None:
        """Validate user-provided longitude/latitude arrays, if provided."""
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

    @classmethod
    def from_track(
        cls,
        data: SWXData,
        flavor: Flavor,
        lon_resolution: float = 1.0,
        lat_resolution: float = 1.0,
    ) -> "GenericGeoMap":
        """Create a GenericGeoMap from raw track data in a SWXData object."""

        flavor_mask = np.zeros(shape=(32, 2), dtype=np.bool_)

        for this_flavor in [0, 1]:
            for this_id in np.arange(32):
                print(f"{this_flavor=}, {this_id=}")
                print(data["observation_flavors"].data[this_id, this_flavor])
                if f"Flavor {flavor}" in str(
                    data["observation_flavors"].data[this_id, this_flavor]
                ):
                    flavor_mask[this_id, this_flavor] = True
        print(flavor_mask)
        if not np.any(flavor_mask):
            raise ValueError(f"Flavor {flavor} not found in data observation_flavors.")
        num_matches = np.sum(flavor_mask)

        print(f"Found {num_matches} observations matching flavor {flavor}.")

        lat = data["lat"].data * u.deg
        lon = data["lon"].data * u.deg
        alt = data["alt"].data * u.km
        coord = EarthLocation(lon=lon, lat=lat, height=alt)
        time = data["time"]

        # Create coordinate grids
        lon_bins = (
            np.arange(-180, 180, lon_resolution) + lon_resolution / 2
        )  # bin centers
        lat_bins = np.arange(-90, 90, lat_resolution) + lat_resolution / 2
        xylon, xylat = np.meshgrid(lon_bins, lat_bins)

        flavor_data = (
            data["observations"].data * flavor_mask[None, :, :]
        )  # [ntimes, nsats, ndos]

        m = np.histogram2d(
            lon.value.flatten(),
            lat.value.flatten(),
            bins=[lon_bins, lat_bins],
            weights=flavor_data[:, :, 0].flatten(),  # Example: using the first dos
        )[0]

        plotTitlePre = str(
            np.min(time).strftime("%d %b %Y %H:%M")
            + " - "
            + np.max(time).strftime("%d %b %Y %H:%M")
        )

        SAA = m
        PC = m
        outrad = m
        slot = m

        dataToPlot = 1
        pltdos = ""

        newv = {
            "xylon": np.transpose(xylon),
            "xylat": np.transpose(xylat),
            "SAA": SAA,
            "PC": PC,
            "outrad": outrad,
            "slot": slot,
            "plotTitlePre": plotTitlePre,
            "dataToPlot": dataToPlot,
            "pltdos": pltdos,
        }  # TODO should load into a SWXData object instead

        return newv

        dosA = tst[:, :, 0]
        dosB = tst[:, :, 1]
        # dosC = tst[:, :, 2] if tst.shape[2] > 2 else None

        pltdos = "dA"
        if pltdos == "dA":
            dos = dosA
        else:
            dos = dosB

        n_times, n_sats = dos.shape

        lookuplon, lookuplat, glook = load_regions()

        # Create 2D region grid
        region_grid = np.zeros((360, 180), dtype=int)
        lon_indices = ((lookuplon + 180) % 360).astype(int)
        lat_indices = (lookuplat + 90).astype(int)
        region_grid[lon_indices, lat_indices] = glook

        # Grid the data using vectorized operations
        # Initialize as lists to collect all values per bin
        dos_bins = [[[] for _ in range(180)] for _ in range(360)]

        for t in range(n_times):
            for s in range(n_sats):
                dos_val = dos[t, s]
                lat_val = lat[t, s]
                lon_val = lon[t, s]
                if not np.isnan(lat_val) and not np.isnan(lon_val):  # Allow nans in dos
                    # Convert to grid indices
                    lon_idx = int((lon_val + 180) % 360)
                    lat_idx = int(lat_val + 90)

                    # Ensure indices are within bounds
                    if 0 <= lon_idx < 360 and 0 <= lat_idx < 180:
                        dos_bins[lon_idx][lat_idx].append(dos_val)

        # Compute medians
        gridded_dos = np.zeros((360, 180)) * np.nan
        for i in range(360):
            for j in range(180):
                if dos_bins[i][j]:
                    gridded_dos[i, j] = np.nanmedian(dos_bins[i][j])

        # Assign to regions using masks
        SAA = np.zeros((360, 180)) * np.nan
        PC = np.zeros((360, 180)) * np.nan
        outrad = np.zeros((360, 180)) * np.nan
        slot = np.zeros((360, 180)) * np.nan

        saa_mask = (region_grid == 1) | (region_grid == -1)
        pc_mask = (region_grid == 2) | (region_grid == -2)
        outrad_mask = (region_grid == 3) | (region_grid == -3)
        slot_mask = (region_grid == 4) | (region_grid == -4)

        SAA[saa_mask] = gridded_dos[saa_mask]
        PC[pc_mask] = gridded_dos[pc_mask]
        outrad[outrad_mask] = gridded_dos[outrad_mask]
        slot[slot_mask] = gridded_dos[slot_mask]

        # Set inf and limiting values to nan
        for arr in [SAA, PC, outrad, slot]:
            badinf = np.where(np.isinf(arr))
            arr[badinf] = np.nan
            # Also set very large values to nan (assuming limiting is >1e30)
            large_vals = np.where(np.abs(arr) > 1e30)
            arr[large_vals] = np.nan

        # Create coordinate grids
        # lon_bins = np.arange(-180, 180, 1) + 0.5  # bin centers
        # lat_bins = np.arange(-90, 90, 1) + 0.5
        # xylon, xylat = np.meshgrid(lon_bins, lat_bins)

        plotTitlePre = str(
            np.min(Epoch).strftime("%d %b %Y %H:%M")
            + " - "
            + np.max(Epoch).strftime("%d %b %Y %H:%M")
        )

        newv = {
            "xylon": np.transpose(xylon),
            "xylat": np.transpose(xylat),
            "SAA": SAA,
            "PC": PC,
            "outrad": outrad,
            "slot": slot,
            "plotTitlePre": plotTitlePre,
            "dataToPlot": dataToPlot,
            "pltdos": pltdos,
        }  # TODO should load into a SWXData object instead

        return newv
