import csv
from pathlib import Path
from typing import Any, Sequence

import matplotlib.path as mpath
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from cartopy import crs as ccrs
from swxsoc.util import create_science_filename, parse_science_filename

from swxsoc_reach import _data_directory

__all__ = [
    "compute_region_code",
    "contour_image_to_path",
    "create_reach_filename",
    "generate_region_contour_data",
    "load_regions",
    "parse_science_filename",
    "plot_region_contours",
    "plot_regions",
]


def load_regions() -> tuple[
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.int_],
]:
    """Load region longitudes, latitudes, and integer region codes."""
    REGION_FILE = _data_directory / "region_file.csv"
    lookuplon: list[float] = []
    lookuplat: list[float] = []
    glook: list[int] = []
    with open(REGION_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            lookuplon.append(float(row[2]))  # lon deg
            lookuplat.append(float(row[1]))  # lat deg
            glook.append(int(row[10]))  # Region Code
    return (
        np.array(lookuplon, dtype=float),
        np.array(lookuplat, dtype=float),
        np.array(glook, dtype=int),
    )


def _nearest_indices(
    values: npt.NDArray[np.float64], query: npt.NDArray[np.float64]
) -> npt.NDArray[np.int_]:
    """Return indices of nearest values for each query element."""
    if values.size == 1:
        return np.zeros(query.shape, dtype=int)

    idx = np.searchsorted(values, query)
    idx = np.clip(idx, 1, values.size - 1)
    left = values[idx - 1]
    right = values[idx]
    use_left = np.abs(query - left) <= np.abs(right - query)
    idx[use_left] -= 1
    return idx


def compute_region_code(lon: npt.ArrayLike, lat: npt.ArrayLike) -> npt.NDArray[np.int_]:
    """Map lon/lat points to integer region codes using nearest lookup points."""
    lookuplon, lookuplat, glook = load_regions()

    lon_values = np.unique(lookuplon)
    lat_values = np.unique(lookuplat)
    region_grid = np.full((lat_values.size, lon_values.size), np.nan)

    lon_index = {value: index for index, value in enumerate(lon_values)}
    lat_index = {value: index for index, value in enumerate(lat_values)}
    for lon_value, lat_value, region_code in zip(
        lookuplon,
        lookuplat,
        glook,
        strict=False,
    ):
        region_grid[lat_index[lat_value], lon_index[lon_value]] = region_code

    # Normalize longitude to match region table domain.
    lon_arr = np.asarray(lon, dtype=float)
    lon_norm = ((lon_arr + 180.0) % 360.0) - 180.0
    lat_arr = np.asarray(lat, dtype=float)

    lon_idx = _nearest_indices(lon_values, lon_norm)
    lat_idx = _nearest_indices(lat_values, lat_arr)
    codes = region_grid[lat_idx, lon_idx]

    # Fill any unmapped points with 0 (outside known region table points).
    return np.nan_to_num(codes, nan=0).astype(int)


def contour_image_to_path(
    image: npt.ArrayLike,
    contour_level: float,
    x_values: npt.ArrayLike | None = None,
    y_values: npt.ArrayLike | None = None,
    ax: Any | None = None,
) -> mpath.Path | None:
    """Convert one contour level from an image into a matplotlib path.

    Parameters
    ----------
    image : array-like
        2D scalar image to contour.
    contour_level : float
        Contour level to extract.
    x_values : array-like, optional
        X-axis coordinates for image columns.
    y_values : array-like, optional
        Y-axis coordinates for image rows.
    ax : matplotlib.axes.Axes, optional
        Existing axis for contour extraction.

    Returns
    -------
    matplotlib.path.Path | None
        Single or compound path for this contour level.
        Returns None if no segments are found.
    """
    image2d = np.asarray(image, dtype=float)
    if image2d.ndim != 2:
        raise ValueError("image must be a 2D array.")

    if x_values is None:
        x_values = np.arange(image2d.shape[1], dtype=float)
    if y_values is None:
        y_values = np.arange(image2d.shape[0], dtype=float)

    created_fig = False
    if ax is None:
        fig, ax = plt.subplots()
        created_fig = True

    contour = ax.contour(
        np.asarray(x_values, dtype=float),
        np.asarray(y_values, dtype=float),
        image2d,
        levels=[float(contour_level)],
    )

    paths: list[mpath.Path] = []
    for segment in contour.allsegs[0]:
        vertices = np.asarray(segment, dtype=float)
        if vertices.shape[0] < 3:
            continue
        paths.append(mpath.Path(vertices, closed=True))

    if created_fig:
        plt.close(fig)

    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]
    return mpath.Path.make_compound_path(*paths)


def generate_region_contour_data(
    ax: Any | None = None,
    contour_levels: Sequence[float] | None = None,
) -> mpath.Path | None:
    """Generate a matplotlib path object from the region CSV table.

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        Existing axis to draw contours on. If None, a new figure and axis
        are created.
    contour_levels : sequence of float, optional
        Contour levels to generate. Defaults to REACH region code levels.

    Returns
    -------
    matplotlib.path.Path | None
        A compound path built from contour segments.
        Returns None when no region points are available.
    """
    lookuplon, lookuplat, glook = load_regions()
    if lookuplon.size == 0:
        return None

    if contour_levels is None:
        contour_levels = (-4, -3, -2, -1, 1, 2, 3, 4)

    lon_values = np.unique(lookuplon)
    lat_values = np.unique(lookuplat)
    region_grid = np.full((lat_values.size, lon_values.size), np.nan)

    lon_index = {value: index for index, value in enumerate(lon_values)}
    lat_index = {value: index for index, value in enumerate(lat_values)}

    for lon_value, lat_value, region_code in zip(
        lookuplon,
        lookuplat,
        glook,
        strict=False,
    ):
        region_grid[lat_index[lat_value], lon_index[lon_value]] = region_code

    paths: list[mpath.Path] = []
    for level in contour_levels:
        path = contour_image_to_path(
            image=region_grid,
            contour_level=float(level),
            x_values=lon_values,
            y_values=lat_values,
            ax=ax,
        )
        if path is not None:
            paths.append(path)

    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]
    return mpath.Path.make_compound_path(*paths)


def plot_regions(
    fileout: str | Path,
    show: bool = False,
    title: str = "REACH Region Map",
    draw_coastlines: bool = True,
    region_names: tuple[str, ...] | None = None,
) -> Path | None:
    """Plot the region map returned by :func:`load_regions` and save it."""
    lookuplon, lookuplat, glook = load_regions()
    if lookuplon.size == 0:
        return None

    region_specs = [
        ("SAA and Inner Zone", (1, -1), "#cd594a"),
        ("Polar Cap", (2, -2), "#efd469"),
        ("Outer Zone", (3, -3), "#093145"),
        ("Slot", (4, -4), "#b5c689"),
    ]
    selected_names = None
    if region_names is not None:
        selected_names = {name.casefold() for name in region_names}

    fig = plt.figure(figsize=(11.69, 8.27))
    ax: Any = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_global()
    if draw_coastlines:
        ax.coastlines()

    ax.gridlines(
        draw_labels=True,
        xlocs=np.arange(-180, 181, 30),
        ylocs=np.arange(-90, 91, 10),
        color="gray",
        linestyle="--",
    )

    for label, codes, color in region_specs:
        if selected_names is not None and label.casefold() not in selected_names:
            continue
        mask = np.isin(glook, codes)
        if np.any(mask):
            ax.scatter(
                lookuplon[mask],
                lookuplat[mask],
                s=8,
                c=color,
                label=label,
                linewidths=0,
                alpha=0.85,
                transform=ccrs.PlateCarree(),
            )

    ax.set_title(title, fontdict={"fontsize": 15})
    ax.legend(loc="lower left", frameon=True)

    output_path = Path(fileout)
    fig.savefig(output_path, orientation="landscape", bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)
    return output_path


def plot_region_contours(
    fileout: str | Path,
    show: bool = False,
    title: str = "REACH Region Code Contours",
    draw_coastlines: bool = True,
) -> Path | None:
    """Plot labeled line contours for the integer region-code grid."""
    from swxsoc_reach.visualization.viz import plot_region_code_contours_on_geomap

    fig = plt.figure(figsize=(11.69, 8.27))
    ax: Any = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax, contour = plot_region_code_contours_on_geomap(
        ax=ax,
        draw_coastlines=draw_coastlines,
        draw_gridlines=True,
        label_contours=True,
    )

    if contour is None:
        plt.close(fig)
        return None

    ax.set_title(title, fontdict={"fontsize": 15})

    output_path = Path(fileout)
    fig.savefig(output_path, orientation="landscape", bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)
    return output_path


def create_reach_filename(
    time: str,
    level: str,
    version: str,
    mode: str = "",
    descriptor: str = "",
    test: bool = False,
):
    """
    Generate the REACH filename based on the provided parameters.

    Parameters
    ----------
    time : Time
        The time associated with the data.
    level : str
        The data level (e.g., "L1", "L2").
    descriptor : str
        The data descriptor (e.g., "SCI", "CAL").
    test : str
        The test identifier (e.g., "TEST1", "TEST2").
    overwrite : bool
        Whether to overwrite existing files.

    Returns
    -------
    str
        The generated REACH filename.
    """
    # Filename Version X.Y.Z comes from two parts:
    #   1. Files Version Base: X.Y comes from the Software Version ->
    #      Data Version Mapping
    #   2. File Version Incrementor: Z starts at 0 and iterates for each
    #      new version based on what already exists in the filesystem.
    # version_base = "1.0"
    # version_increment = 0
    # version_str = f"{version_base}.{version_increment}"
    version_str = version

    # The Base Filename is used for searching to see if we need to
    # increase our version increment.
    base_filename = create_science_filename(
        instrument="reach",
        time=time,
        level=level,
        version=version_str,
        mode=mode,
        descriptor=descriptor,
        test=test,
    )
    return base_filename
