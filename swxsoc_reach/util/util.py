import csv
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from cartopy import crs as ccrs
from swxsoc.util import create_science_filename, parse_science_filename

from swxsoc_reach import _data_directory

__all__ = [
    "create_reach_filename",
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
    lookuplon, lookuplat, glook = load_regions()
    if lookuplon.size == 0:
        return None

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
        region_grid[
            lat_index[lat_value],
            lon_index[lon_value],
        ] = region_code

    contour_levels = [-4, -3, -2, -1, 1, 2, 3, 4]
    contour_colors = [
        "#6b7280",
        "#093145",
        "#efd469",
        "#cd594a",
        "#cd594a",
        "#efd469",
        "#093145",
        "#b5c689",
    ]

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

    contour = ax.contour(
        lon_values,
        lat_values,
        region_grid,
        levels=contour_levels,
        colors=contour_colors,
        linewidths=1.2,
        transform=ccrs.PlateCarree(),
    )
    ax.clabel(
        contour,
        contour.levels,
        inline=True,
        fmt="%d",
        fontsize=8,
    )

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

