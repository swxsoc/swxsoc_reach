"""
Provides generic file readers.
"""

import json
from pathlib import Path

import pandas as pd

__all__ = ["read_file", "read_udl_json", "read_udl_csv"]


def read_file(file_path: Path) -> pd.DataFrame:
    """
    Reads a file and returns a pandas DataFrame.

    Parameters
    ----------
    file_path : Path
        The path to the file to read.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the data from the file.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    if file_path.suffix.lower() == ".json":
        return read_udl_json(file_path)
    elif file_path.suffix.lower() == ".csv":
        return read_udl_csv(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")


def _unpack_nested_columns(data: pd.DataFrame) -> pd.DataFrame:
    """
    Unpack nested ``seoList`` and ``senPos`` columns into flat columns
    and drop the originals.

    Parameters
    ----------
    data : pd.DataFrame
        DataFrame containing ``seoList`` and ``senPos`` columns.

    Returns
    -------
    pd.DataFrame
        DataFrame with the nested columns replaced by their unpacked values.
    """
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

    return _unpack_nested_columns(data)


def read_udl_csv(file_path: Path) -> pd.DataFrame:
    """
    Reads a UDL CSV file and returns a pandas DataFrame.
    Unpacks nested JSON structures in the CSV into a flat DataFrame.

    Parameters
    ----------
    file_path : Path
        The path to the UDL CSV file.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the data from the UDL CSV file.
    """
    # Convert to Path if not already
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    # Read the CSV file into a DataFrame
    data = pd.read_csv(file_path)

    # Convert the string representation of lists/dicts to actual lists/dicts
    data["seoList"] = data["seoList"].apply(json.loads)
    data["senPos"] = data["senPos"].apply(json.loads)

    return _unpack_nested_columns(data)
