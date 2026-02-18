"""
Core transformation functions for REACH UDL data.

Provides functions to deduplicate records, extract sensor metadata,
build sparse time-aligned arrays, and assemble an SWXData object
ready for CDF output.
"""

import logging

import astropy.units as u
import numpy as np
import pandas as pd
from astropy.nddata import NDData
from astropy.time import Time
from astropy.timeseries import TimeSeries
from swxsoc.swxdata import SWXData

log = logging.getLogger(__name__)

__all__ = [
    "REACH_GLOBAL_ATTRS",
    "deduplicate_records",
    "extract_sensor_metadata",
    "create_observation_array",
    "create_sensor_array",
    "build_swxdata",
]

REACH_GLOBAL_ATTRS: dict = {
    "DOI": "https://doi.org/<PREFIX>/<SUFFIX>",
    "Data_level": "L1>Level 1",
    "Data_version": "1.0.0",
    "Data_product_descriptor": "dosimeter",
    "Descriptor": "reach",
    "Discipline": "Space Physics>Magnetospheric Science",
    "HTTP_LINK": [
        "https://spdf.gsfc.nasa.gov/istp_guide/istp_guide.html",
        "https://spdf.gsfc.nasa.gov/istp_guide/gattributes.html",
        "https://spdf.gsfc.nasa.gov/istp_guide/vattributes.html",
    ],
    "Instrument_mode": "all",
    "Instrument_type": "Particle Flux (space)",
    "LINK_TEXT": ["ISTP Guide", "Global Attrs", "Variable Attrs"],
    "LINK_TITLE": ["ISTP Guide", "Global Attrs", "Variable Attrs"],
    "Mission_group": "REACH",
    "MODS": [
        "v1.0.0 - Original version.",
    ],
    "PI_affiliation": "Aerospace Corporation",
    "PI_name": "TBD",
    "Project": "REACH>Responsive Environmental Assessment Commercially Hosted",
    "Source_name": "REACH>Responsive Environmental Assessment Commercially Hosted",
    "TEXT": "Direct output from UDL",
}


def deduplicate_records(data: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate records, keeping the latest reprocessed entry.

    For each unique combination of ``(idSensor, obDescription, obTime)``,
    only the row with the most recent ``createdAt`` timestamp is retained.
    The returned DataFrame is sorted by ``obTime`` with a reset index.

    Parameters
    ----------
    data : pd.DataFrame
        Raw (flat) DataFrame from :func:`~swxsoc_reach.io.file_tools.read_udl_json`.

    Returns
    -------
    pd.DataFrame
        Deduplicated DataFrame sorted by observation time.
    """
    before = len(data)
    data = (
        data.sort_values("createdAt", ascending=False)
        .drop_duplicates(subset=["idSensor", "obDescription", "obTime"], keep="first")
        .sort_values("obTime")
        .reset_index(drop=True)
    )
    after = len(data)
    log.info("Dropped %d duplicate records (%d → %d)", before - after, before, after)
    return data


def extract_sensor_metadata(
    data: pd.DataFrame,
) -> tuple[list[str], list[str], list[list[str | None]]]:
    """
    Extract sorted sensor IDs, observatory names, and per-sensor flavors.

    Parameters
    ----------
    data : pd.DataFrame
        Deduplicated DataFrame.

    Returns
    -------
    sensor_ids : list[str]
        Sorted list of unique sensor IDs.
    obs_names : list[str]
        Sorted list of unique observatory names.
    observation_flavors : list[list[str | None]]
        For each sensor (matching ``sensor_ids`` order), a list of the
        sorted unique dosimeter flavor strings (``obDescription``),
        padded with ``""`` so that every inner list has the same length
        (equal to the maximum number of flavors across all sensors).
    """
    sensor_ids = sorted([str(s) for s in data["idSensor"].unique()])
    obs_names = sorted([str(n) for n in data["observatoryName"].unique()])

    # Get sorted unique flavors per sensor, ordered by sensor_ids
    flavors_per_sensor = data.groupby("idSensor")["obDescription"].apply(
        lambda x: sorted(x.unique().astype(str).tolist())
    )
    observation_flavors = flavors_per_sensor.reindex(sensor_ids).tolist()

    # Pad to rectangular shape so np.array() succeeds
    max_flavors = max(len(f) for f in observation_flavors)
    observation_flavors = [
        f + [""] * (max_flavors - len(f)) for f in observation_flavors
    ]

    log.info(
        "Found %d sensors, %d observatories, flavors per sensor: %s",
        len(sensor_ids),
        len(obs_names),
        [len(f) for f in observation_flavors],
    )
    return sensor_ids, obs_names, observation_flavors


def create_observation_array(
    data: pd.DataFrame,
    sensor_ids: list[str],
    times_pd: pd.DatetimeIndex,
    observation_flavors: list[list[str]],
) -> np.ndarray:
    """
    Create a sparse observation array for ``obValue``.

    For each sensor and each of its dosimeter flavors, extracts the
    observation values and aligns them to a common time index, filling
    missing entries with NaN.

    Parameters
    ----------
    data : pd.DataFrame
        Deduplicated DataFrame with columns ``idSensor``, ``obDescription``,
        ``obTime``, and ``obValue``.
    sensor_ids : list[str]
        Sorted list of unique sensor IDs.
    times_pd : pd.DatetimeIndex
        Sorted, UTC-localized DatetimeIndex of unique observation times.
    observation_flavors : list[list[str]]
        For each sensor (matching ``sensor_ids`` order), a list of the
        sorted unique dosimeter flavor strings (``obDescription``),
        padded with ``""`` so that every inner list has the same length
        (equal to the maximum number of flavors across all sensors).

    Returns
    -------
    np.ndarray
        3-D float array of shape ``(n_times, n_sensors, 2)`` with NaN for
        missing values.
    """
    # Pre-convert obTime to datetime once for the entire DataFrame
    dt_index = pd.to_datetime(data["obTime"].astype(str))

    # Group by (idSensor, obDescription) once
    grouped = data.groupby(["idSensor", "obDescription"])

    sensor_dfs = []
    for sensor_idx, sensor in enumerate(sensor_ids):
        series_list = []
        n_flavors = len(observation_flavors[sensor_idx])

        for flavor_idx in range(n_flavors):
            expected_flavor = observation_flavors[sensor_idx][flavor_idx]
            key = (sensor, expected_flavor)

            if key in grouped.groups:
                group = grouped.get_group(key)
                s = pd.Series(
                    pd.to_numeric(group["obValue"], errors="coerce").values,
                    index=dt_index[group.index],
                    name=f"flavor_{flavor_idx}",
                )
            else:
                s = pd.Series(
                    dtype=float,
                    index=pd.DatetimeIndex([]).tz_localize("UTC"),
                    name=f"flavor_{flavor_idx}",
                )
            series_list.append(s)

        df = pd.concat(series_list, axis=1)
        df = df.reindex(times_pd)
        sensor_dfs.append(df.values)

    return np.stack(sensor_dfs, axis=1).astype(float)


def create_sensor_array(
    sensor_grouped: pd.core.groupby.DataFrameGroupBy,
    sensor_deduped_dt: pd.Series,
    sensor_ids: list[str],
    times_pd: pd.DatetimeIndex,
    col: str,
) -> np.ndarray:
    """
    Create a sparse per-sensor array for a single column.

    Extracts values of *col* for each sensor from pre-grouped and
    deduplicated data, aligns them to a common time index, and fills
    missing entries with NaN.

    Parameters
    ----------
    sensor_grouped : pd.core.groupby.DataFrameGroupBy
        Pre-computed groupby on ``idSensor`` from the sensor-deduplicated
        DataFrame.
    sensor_deduped_dt : pd.Series
        Datetime-converted ``obTime`` column from the sensor-deduplicated
        DataFrame, sharing the same index so it can be used for alignment.
    sensor_ids : list[str]
        Sorted list of unique sensor IDs.
    times_pd : pd.DatetimeIndex
        Sorted, UTC-localized DatetimeIndex of unique observation times.
    col : str
        Column name to extract (e.g. ``'lat'``, ``'lon'``, ``'alt'``).

    Returns
    -------
    np.ndarray
        2-D float array of shape ``(n_times, n_sensors)`` with NaN for
        missing values.
    """
    sensor_dfs = []
    for sensor in sensor_ids:
        if sensor in sensor_grouped.groups:
            group = sensor_grouped.get_group(sensor)
            s = pd.Series(
                group[col].values,
                index=sensor_deduped_dt[group.index],
                name=sensor,
            )
        else:
            s = pd.Series(dtype=float, index=pd.DatetimeIndex([]), name=sensor)
        sensor_dfs.append(s)

    df = pd.concat(sensor_dfs, axis=1)
    df = df.reindex(times_pd)
    return df.values.astype(float)


def build_swxdata(
    data: pd.DataFrame,
    *,
    version: str = "1.0.0",
    global_attrs: dict | None = None,
) -> SWXData:
    """
    Assemble an :class:`~swxsoc.swxdata.SWXData` object from a deduplicated
    REACH DataFrame.

    This is the main entry point for the transformation layer.  It
    orchestrates deduplication, metadata extraction, sparse-array
    construction, and SWXData packaging in a single call.

    Parameters
    ----------
    data : pd.DataFrame
        Raw (flat) DataFrame as returned by
        :func:`~swxsoc_reach.io.file_tools.read_udl_json`.
        Will be deduplicated internally.
    version : str, optional
        Data version string written into the global attributes
        (default ``"1.0.0"``).
    global_attrs : dict or None, optional
        Override the default :data:`REACH_GLOBAL_ATTRS`.  If *None*,
        the module-level default is used and ``Data_version`` is set
        to *version*.

    Returns
    -------
    SWXData
        Fully assembled SWXData instance ready to be saved as CDF.
    """
    # --- 1. Deduplicate ------------------------------------------------
    data = deduplicate_records(data)

    # --- 2. Sensor metadata --------------------------------------------
    sensor_ids, _obs_names, observation_flavors = extract_sensor_metadata(data)

    # --- 3. Build common time axis -------------------------------------
    times = Time(sorted(data["obTime"].unique())).sort()
    times_pd = pd.DatetimeIndex([t.datetime for t in times]).tz_localize("UTC")

    ts = TimeSeries(time=times)
    ts.time.meta = {
        "CATDESC": "Observation Time",
        "VAR_TYPE": "support_data",
    }

    # --- 4. Pre-compute per-sensor groupby for scalar columns ----------
    sensor_deduped = data.drop_duplicates(subset=["idSensor", "obTime"], keep="first")
    sensor_deduped_dt = pd.to_datetime(sensor_deduped["obTime"].astype(str))
    sensor_grouped = sensor_deduped.groupby("idSensor")

    # --- 5. Build variable dict ----------------------------------------
    variables: dict[str, NDData] = {
        "sensor_ids": NDData(
            data=np.array(sensor_ids),
            meta={"CATDESC": "REACH Sensor IDs", "VAR_TYPE": "metadata"},
        ),
        "observation_flavors": NDData(
            data=np.array(observation_flavors),
            meta={
                "CATDESC": "Observation Flavors per Sensor",
                "VAR_TYPE": "metadata",
            },
        ),
        "observations": NDData(
            data=create_observation_array(
                data, sensor_ids, times_pd, observation_flavors
            ),
            meta={
                "CATDESC": "Observation Values",
                "VAR_TYPE": "data",
                "UNITS": (u.J / u.kg * 0.01).to_string(),
                "DEPEND_0": "Epoch",
            },
        ),
        "lat": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "lat"
            ),
            meta={
                "CATDESC": "Latitude",
                "VAR_TYPE": "data",
                "UNITS": u.degree.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
            },
        ),
        "lon": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "lon"
            ),
            meta={
                "CATDESC": "Longitude",
                "VAR_TYPE": "data",
                "UNITS": u.degree.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
            },
        ),
        "alt": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "alt"
            ),
            meta={
                "CATDESC": "Altitude",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
            },
        ),
        "obQuality": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "obQuality"
            ),
            meta={
                "CATDESC": "Observation Quality",
                "VAR_TYPE": "data",
                "UNITS": u.dimensionless_unscaled.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
            },
        ),
        "senPos0": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "senPos0"
            ),
            meta={
                "CATDESC": "Sensor Position 0",
                "VAR_TYPE": "data",
                "UNITS": u.dimensionless_unscaled.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
            },
        ),
        "senPos1": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "senPos1"
            ),
            meta={
                "CATDESC": "Sensor Position 1",
                "VAR_TYPE": "data",
                "UNITS": u.dimensionless_unscaled.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
            },
        ),
        "senPos2": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "senPos2"
            ),
            meta={
                "CATDESC": "Sensor Position 2",
                "VAR_TYPE": "data",
                "UNITS": u.dimensionless_unscaled.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
            },
        ),
    }

    # --- 6. Global attributes ------------------------------------------
    if global_attrs is None:
        global_attrs = {**REACH_GLOBAL_ATTRS, "Data_version": version}

    # --- 7. Assemble SWXData -------------------------------------------
    reach_data = SWXData(timeseries=ts, support=variables, meta=global_attrs)
    log.info(
        "Built SWXData: %d time steps, %d sensors, %d support variables",
        len(ts),
        len(sensor_ids),
        len(variables),
    )
    return reach_data
