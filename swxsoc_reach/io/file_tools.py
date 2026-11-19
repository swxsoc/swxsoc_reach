"""
Provides generic file readers.
"""

import ast
import json
from pathlib import Path

import pandas as pd
from astropy.time import Time
from swxsoc.swxdata import SWXData

from swxsoc_reach import log
from swxsoc_reach.util.util import LEGACY_PIPELINE_TIME_FORMAT

__all__ = ["read_file", "read_udl_json", "read_udl_csv"]


def read_file(file_path: Path) -> pd.DataFrame | SWXData:
    """
    Reads a file and returns a pandas DataFrame or SWXData object.

    Parameters
    ----------
    file_path : Path
        The path to the file to read.

    Returns
    -------
    pd.DataFrame | SWXData
        A DataFrame or SWXData object containing the data from the file.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    if file_path.suffix.lower() == ".json":
        return read_udl_json(file_path)
    elif file_path.suffix.lower() == ".csv":
        return read_udl_csv(file_path)
    elif file_path.suffix.lower() in ".cdf":
        return SWXData.load(file_path)
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

    # Convert the string representation of lists/dicts to actual lists/dicts.
    # ast.literal_eval handles both single-quoted (Python repr) and double-quoted (JSON) formats.
    data["seoList"] = data["seoList"].apply(ast.literal_eval)
    data["senPos"] = data["senPos"].apply(ast.literal_eval)

    # Record the source file name for traceability / provenance
    data["source_file"] = Path(file_path).name

    return _unpack_nested_columns(data)


def read_legacy_csv(file_path: Path) -> pd.DataFrame:
    """
    Read one Legacy CSV and add a naive UTC obTime built from YYYY, mm, DD, HH, MM, SEC.

    Columns of the Legacy CSV are defined in the TOR data dictionary:
    https://zenodo.org/records/6423507?preview_file=TOR-2021-01076.pdf

    Parameters
    ----------
    file_path : Path
        The path to the Legacy CSV file.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the data from the Legacy CSV file with an added obTime column.
    """
    df = pd.read_csv(file_path)
    # Construct a naive UTC datetime from the separate date and time columns
    base = pd.to_datetime(dict(year=df["YYYY"], month=df["mm"], day=df["DD"]))
    df["obTime"] = (
        base
        + pd.to_timedelta(df["HH"], unit="h")
        + pd.to_timedelta(df["MM"], unit="m")
        + pd.to_timedelta(df["SEC"], unit="s")
    )

    # Record the source file name for traceability / provenance
    df["source_file"] = Path(file_path).name

    return df


def read_legacy_pipeline_files(day_files: list[Path]) -> pd.DataFrame:
    """
    Read and concatenate all Legacy files for one UTC day, skipping empty or unreadable files.
    Parameters
    ----------
    day_files : list[Path]
        A list of file paths of the Legacy CSV files for the day.

    Returns
    -------
    pd.DataFrame
        A concatenated DataFrame containing the data from all readable Legacy CSV files for the day.
    """
    frames = []
    for file_path in day_files:
        try:
            df = read_legacy_csv(file_path)
        except Exception as exc:
            log.warning(f"Skipping unreadable Legacy file {file_path}: {exc}")
            continue
        if df.empty:
            log.warning(f"Skipping empty Legacy file {file_path}")
            continue
        frames.append(df)

    if not frames:
        raise ValueError("No readable Legacy files for this day")

    # Concatenate all DataFrames into one
    concated_df = pd.concat(frames, ignore_index=True)
    # Sort the concatenated DataFrame by obTime
    sorted_df = concated_df.sort_values(by="obTime", inplace=False)

    return sorted_df


def read_legacy_pipeline_day(data_dir: Path, day: Time) -> pd.DataFrame:
    """
    Load all Legacy pipeline files for a specific UTC day.

    Ex filename: reach.20260801.vid-101.l1b.v3.csv

    Parameters
    ----------
    data_dir : Path
        The directory containing the Legacy pipeline files.
    day : Time
        The specific UTC day to load files for.

    Returns
    -------
    pd.DataFrame
        A concatenated DataFrame containing the data from all readable Legacy CSV files for the specified day.
    """
    # Generate the expected filename pattern for the given day
    day_str = day.strftime(LEGACY_PIPELINE_TIME_FORMAT)
    pattern = f"reach.{day_str}.*.csv"

    # Find all matching files in the data directory
    day_files = list(data_dir.glob(pattern))

    if not day_files:
        raise FileNotFoundError(
            f"No Legacy pipeline files found for {day_str} in {data_dir}"
        )

    return read_legacy_pipeline_files(day_files)
