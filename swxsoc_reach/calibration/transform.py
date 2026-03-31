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

from swxsoc_reach.util.schema import REACHDataSchema

log = logging.getLogger(__name__)

__all__ = [
    "deduplicate_records",
    "extract_sensor_metadata",
    "create_observation_array",
    "create_sensor_array",
    "build_swxdata",
]


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
        3-D float array of shape ``(n_times, n_sensors, n_flavors_max)`` with
        NaN for missing values, where ``n_flavors_max`` is the maximum number
        of dosimeter flavors across all sensors and the last dimension indexes
        those flavors for each sensor.
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
    Assemble an :class:`~swxsoc.swxdata.SWXData` object from a raw REACH DataFrame.

    This is the main entry point for the transformation layer.  It runs
    the following pipeline in order:

    1. **Deduplicate** records via :func:`deduplicate_records`.
    2. **Extract sensor metadata** (sensor IDs, observatory names, flavors)
       via :func:`extract_sensor_metadata`.
    3. **Build common time axis** from the unique UTC observation timestamps,
       stripping any trailing ``Z`` before parsing to avoid a stack overflow
       in astropy's recursive ISO-8601 parser for large arrays.
    4. **Pre-compute per-sensor groupby** on a sensor-deduplicated view of
       the data for efficient scalar-column extraction.
    5. **Build variable dict** of :class:`~astropy.nddata.NDData` arrays
       (observations, attitude, quality, sensor-position, and label variables).
    6. **Seed global attributes** from :class:`~swxsoc_reach.util.schema.REACHDataSchema`
       defaults, then overlay *version* and any caller-supplied *global_attrs*.
    7. **Assemble and return** a :class:`~swxsoc.swxdata.SWXData` instance
       ready to be written to CDF.

    The returned :class:`~swxsoc.swxdata.SWXData` contains:

    ========================  ==========================================
    Variable                  Shape
    ========================  ==========================================
    ``Epoch``                 ``(n_times,)``
    ``Epoch_label``           ``(n_times,)``
    ``sensor_ids``            ``(n_sensors,)``
    ``observation_flavors``   ``(n_sensors, n_flavors_max)``
    ``Flavor_label``          ``(n_flavors_max,)``
    ``observations``          ``(n_times, n_sensors, n_flavors_max)``
    ``lat``                   ``(n_times, n_sensors)``
    ``lon``                   ``(n_times, n_sensors)``
    ``alt``                   ``(n_times, n_sensors)``
    ``obQuality``             ``(n_times, n_sensors)``
    ``senPos0``               ``(n_times, n_sensors)``
    ``senPos1``               ``(n_times, n_sensors)``
    ``senPos2``               ``(n_times, n_sensors)``
    ========================  ==========================================

    Parameters
    ----------
    data : pd.DataFrame
        Raw (flat) DataFrame as returned by
        :func:`~swxsoc_reach.io.file_tools.read_udl_json` or
        :func:`~swxsoc_reach.io.file_tools.read_udl_csv`.
    version : str, optional
        Data version string written into the global attributes
        (default ``"1.0.0"``).
    global_attrs : dict or None, optional
        Additional global attributes to merge on top of the defaults
        provided by :class:`~swxsoc_reach.util.schema.REACHDataSchema`.
        ``Data_version`` is always set to *version*.

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
    # Strip trailing 'Z' and pass explicit scale/format to avoid a stack
    # overflow in astropy's recursive ISO-8601 parser for large arrays.
    unique_times_raw = sorted(data["obTime"].unique())
    unique_times = [t[:-1] if t.endswith("Z") else t for t in unique_times_raw]
    times = Time(unique_times, scale="utc", format="isot").sort()
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
        "Flavor_label": NDData(
            data=np.array(
                [f"flavor_{i}" for i in range(len(observation_flavors[0]))]
            ),  # Assuming all sensors have the same max flavor count due to padding
            meta={
                "CATDESC": "Label for observation_flavors dimension",
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
                "LABL_PTR_1": "sensor_ids",
                "LABL_PTR_2": "Flavor_label",
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
                "LABL_PTR_1": "sensor_ids",
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
                "LABL_PTR_1": "sensor_ids",
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
                "LABL_PTR_1": "sensor_ids",
            },
        ),
        "obQuality": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "obQuality"
            ),
            meta={
                "CATDESC": "Observation Quality",
                "VAR_TYPE": "data",
                "UNITS": "unitless",
                "DEPEND_0": "Epoch",
                "LABL_PTR_1": "sensor_ids",
            },
        ),
        "sensor_position_x": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "senPos0"
            ),
            meta={
                "CATDESC": "GEI Coordinate Position X in KM",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "LABL_PTR_1": "sensor_ids",
            },
        ),
        "sensor_position_y": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "senPos1"
            ),
            meta={
                "CATDESC": "GEI Coordinate Position Y in KM",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "LABL_PTR_1": "sensor_ids",
            },
        ),
        "sensor_position_z": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_ids, times_pd, "senPos2"
            ),
            meta={
                "CATDESC": "GEI Coordinate Position Z in KM",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "LABL_PTR_1": "sensor_ids",
            },
        ),
    }

    # --- 6. Global attributes ------------------------------------------
    # Seed meta with schema defaults, then overlay dynamic per-file values.
    # SWXData.__init__ requires Descriptor, Data_level, Data_version upfront.
    schema = REACHDataSchema()
    meta = dict(schema.default_global_attributes)
    meta["Data_version"] = version
    if global_attrs is not None:
        meta.update(global_attrs)

    # --- 7. Assemble SWXData -------------------------------------------
    reach_data = SWXData(timeseries=ts, support=variables, meta=meta, schema=schema)

    log.info(
        "Built SWXData: %d time steps, %d sensors, %d support variables",
        len(ts),
        len(sensor_ids),
        len(variables),
    )
    return reach_data
