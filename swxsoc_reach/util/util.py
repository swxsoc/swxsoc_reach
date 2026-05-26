import csv
from pathlib import Path

import numpy as np
import numpy.typing as npt
from astropy.time import Time
from swxsoc.util.util import TIME_FORMAT, parse_science_filename

from swxsoc_reach import _data_directory
from swxsoc_reach.util.geom import contour_image_to_path  # noqa: F401

__all__ = [
    "contour_image_to_path",
    "create_reach_filename",
    "load_regions",
    "parse_science_filename",
    "TIME_FORMAT",
]


def load_regions(
    file_path: str | Path | None = None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.int_]]:
    """
    Load region longitudes, latitudes, and integer region codes.

    Parameters
    ----------
    file_path : str, Path, or None, optional
        Path to the region CSV file. If None, uses the default region file in the data directory.

    Returns
    -------
    tuple of (npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.int_])
        A tuple containing:
        - Longitudes array (float64)
        - Latitudes array (float64)
        - Integer region codes array (int)
    """
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


def get_reachid_lut() -> dict[str, dict[str, str]]:
    """
    Return a lookup table mapping Iridium satellite names to REACH IDs and POD model numbers.

    Returns
    -------
    dict[str, dict[str, str]]
        A dictionary where keys are Iridium satellite names (e.g., 'Iridium-102') and values are
        dictionaries containing 'reachid' and 'pod_model' keys with their corresponding string values.
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
) -> str:
    """Generate the REACH filename based on the provided parameters.

    Parameters
    ----------
    time : str
        The time associated with the data in ISO format.
    level : str
        The data level (e.g., "L1", "L2").
    version : str
        The version string (e.g., "0.0.1") in major.minor.patch format.
        Should come from the global attribute `Data_version`.
    mode : str, optional
        The instrument mode (e.g., "all"). Default is empty string.
        Should come from the global attribute `Instrument_mode`.
    descriptor : str, optional
        The dataset descriptor (e.g., "prelim"). Default is empty string.
        Should come from the global attribute `Data_type`.

    Returns
    -------
    str
        The generated REACH filename in CDF format (e.g., "reach_all_L1_prelim_20250612T000000_v1.0.0.cdf").
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
