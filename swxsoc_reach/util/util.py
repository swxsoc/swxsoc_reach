import csv
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from astropy.time import Time
from cartopy import crs as ccrs
from swxsoc.util.util import TIME_FORMAT, parse_science_filename

from swxsoc_reach import _data_directory
from swxsoc_reach.util.enums import Region
from swxsoc_reach.util.geom import contour_image_to_path  # noqa: F401

__all__ = [
    "contour_image_to_path",
    "create_reach_filename",
    "load_regions",
    "parse_science_filename",
    "plot_region_contours",
    "plot_regions",
    "TIME_FORMAT",
]


def load_regions(
    file_path: str | Path | None = None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.int_]]:
    """Load region longitudes, latitudes, and integer region codes."""
    region_file = (
        Path(file_path)
        if file_path is not None
        else _data_directory / "region_file.csv"
    )

    lookuplon: list[float] = []
    lookuplat: list[float] = []
    glook: list[int] = []

    with region_file.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            lookuplon.append(float(row[2]))
            lookuplat.append(float(row[1]))
            glook.append(int(row[10]))

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
        (region.label, region.signed_codes, region.color) for region in Region.ordered()
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
    from swxsoc_reach.visualization.viz import plot_geomap

    fig = plt.figure(figsize=(11.69, 8.27))
    ax: Any = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax, contour = plot_geomap(
        ax=ax,
        draw_coastlines=draw_coastlines,
        draw_gridlines=True,
        draw_contours=True,
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
def get_reachid_lut():
    """
    Function to return a lookup table (dictionary) mapping Iridium satellite names to their corresponding REACH IDs and POD model numbers.

    Returns
    -------
    dict
        A dictionary where the keys are Iridium satellite names (e.g., 'Iridium-102') and the values are dictionaries containing 'reachid' and 'pod_model' keys with their corresponding values.
    """

    reachids = {
        "Iridium-102": {"reachid": "REACH-101", "pod_model": "1"},
        "Iridium-113": {"reachid": "REACH-102", "pod_model": "2"},
        "Iridium-106": {"reachid": "REACH-105", "pod_model": "3"},
        "Iridium-133": {"reachid": "REACH-108", "pod_model": "1"},
        "Iridium-121": {"reachid": "REACH-113", "pod_model": "2"},
        "Iridium-110": {"reachid": "REACH-114", "pod_model": "1"},
        "Iridium-107": {"reachid": "REACH-115", "pod_model": "1"},
        "Iridium-108": {"reachid": "REACH-116", "pod_model": "2"},
        "Iridium-117": {"reachid": "REACH-133", "pod_model": "1"},
        "Iridium-125": {"reachid": "REACH-134", "pod_model": "3"},
        "Iridium-126": {"reachid": "REACH-135", "pod_model": "1"},
        "Iridium-132": {"reachid": "REACH-136", "pod_model": "1"},
        "Iridium-119": {"reachid": "REACH-137", "pod_model": "1"},
        "Iridium-134": {"reachid": "REACH-138", "pod_model": "3"},
        "Iridium-137": {"reachid": "REACH-139", "pod_model": "1"},
        "Iridium-122": {"reachid": "REACH-140", "pod_model": "2"},
        "Iridium-131": {"reachid": "REACH-148", "pod_model": "2"},
        "Iridium-164": {"reachid": "REACH-149", "pod_model": "1"},
        "Iridium-147": {"reachid": "REACH-162", "pod_model": "1"},
        "Iridium-149": {"reachid": "REACH-163", "pod_model": "2"},
        "Iridium-152": {"reachid": "REACH-164", "pod_model": "1"},
        "Iridium-145": {"reachid": "REACH-165", "pod_model": "3"},
        "Iridium-180": {"reachid": "REACH-166", "pod_model": "2"},
        "Iridium-153": {"reachid": "REACH-169", "pod_model": "0"},
        "Iridium-156": {"reachid": "REACH-170", "pod_model": "0"},
        "Iridium-158": {"reachid": "REACH-171", "pod_model": "0"},
        "Iridium-159": {"reachid": "REACH-172", "pod_model": "0"},
        "Iridium-165": {"reachid": "REACH-173", "pod_model": "1"},
        "Iridium-168": {"reachid": "REACH-175", "pod_model": "3"},
        "Iridium-150": {"reachid": "REACH-176", "pod_model": "1"},
        "Iridium-171": {"reachid": "REACH-180", "pod_model": "0"},
        "Iridium-160": {"reachid": "REACH-181", "pod_model": "0"},
    }

    return reachids


def create_reach_filename(
    time: str,
    level: str,
    version: str,
    mode: str = "",
    descriptor: str = "",
):
    """
    Generate the REACH filename based on the provided parameters.

    Parameters
    ----------
    time : str
        The time associated with the data.
    level : str
        The data level (e.g., "L1", "L2").
    version : str
        The version string (e.g., "0.0.1"). This should be in the format major.minor.patch.
        This should come from the global attribute `Data_version`.
    mode : str
        The instrument mode (e.g., "all"). This should come from the global attribute `Instrument_mode`.
    descriptor : str
        The dataset descriptor (e.g., "prelim"). This should come from the global attribute `Data_type`.

    Returns
    -------
    str
        The generated REACH filename.
    """
    # Define Static Parts
    instrument_shortname = "reach"

    # Format Time String
    start_time = Time(time, format="isot")
    time_str = start_time.strftime(TIME_FORMAT)

    # Combine Parts into Filename
    filename = (
        f"{instrument_shortname}_{mode}_{level}_{descriptor}_{time_str}_v{version}.cdf"
    )
    filename = filename.replace("__", "_")  # reformat if mode or descriptor not given

    return filename
