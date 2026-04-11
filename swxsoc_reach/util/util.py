import csv

import numpy as np
from swxsoc.util import create_science_filename, parse_science_filename

from swxsoc_reach import _data_directory

__all__ = [
    "create_reach_filename",
    "parse_science_filename",
]


def load_regions() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load region data from the CSV file and return the longitude, latitude, and region code arrays."""
    REGION_FILE = _data_directory / "region_file.csv"
    lookuplon, lookuplat, glook = [], [], []
    with open(REGION_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            lookuplon.append(float(row[2]))  # lon deg
            lookuplat.append(float(row[1]))  # lat deg
            glook.append(int(row[10]))  # Region Code
    return np.array(lookuplon), np.array(lookuplat), np.array(glook)


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
    #   1. Files Version Base: X.Y comes from the Software Version -> Data Version Mapping
    #   2. File Version Incrementor: Z starts at 0 and iterates for each new version based on what already exists in the filesystem.
    # version_base = "1.0"
    # version_increment = 0
    # version_str = f"{version_base}.{version_increment}"
    version_str = version

    # The Base Filename is used for searching to see if we need to increase our version increment.
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
