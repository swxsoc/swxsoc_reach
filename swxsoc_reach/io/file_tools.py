"""
Provides generic file readers.
"""

from pathlib import Path

import json
import pandas as pd
import astropy.io.fits as fits
from astropy.io import ascii
from astropy.time import Time
from astropy.timeseries import TimeSeries

__all__ = ["read_file", "read_raw_file", "read_fits"]


def read_udl_json(file_path: Path) -> pd.DataFrame:
    """
    Reads a UDL JSON file and returns a pandas DataFrame.
    Unpacks nested JSON structures into a flat DataFrame.

    Parameters
    ----------
    file_path : Path
        The path to the UDL JSON file.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the data from the UDL JSON file.
    """
    # Convert to Path if not already
    if not isinstance(file_path, Path):
        file_path = Path(file_path)
    try:
        data = pd.read_json(file_path)
    except ValueError:
        # pd.read_json uses ujson which can fail on very small or very large numeric values;
        # fall back to the standard library json parser.
        with open(file_path, "r") as file:
            data = pd.DataFrame(json.load(file))
            
    # Unpack Nested Data Fields in the JSON Structure

    # Unpack seoList
    data["obDescription"] = data["seoList"].apply(lambda x: x[0]["obDescription"])
    data["obValue"] = data["seoList"].apply(lambda x: x[0]["obValue"])
    data["obQuality"] = data["seoList"].apply(lambda x: x[0]["obQuality"])

    # Unpack senPos
    for i in range(3):
        data[f"senPos{i}"] = data["senPos"].apply(lambda x: x[i])
        
    # Drop previously nested columns
    data = data.drop(columns=["seoList", "senPos"])

    return data