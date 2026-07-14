"""
Core transformation functions for REACH UDL data.

Provides functions to deduplicate records, extract sensor metadata,
build sparse time-aligned arrays, and assemble an SWXData object
ready for CDF output.
"""

import re

import astropy.units as u
import numpy as np
import pandas as pd
from astropy.nddata import NDData
from astropy.time import Time
from astropy.timeseries import TimeSeries
from swxsoc.swxdata import SWXData

from swxsoc_reach import log
from swxsoc_reach.util.enums import (
    Flavor,
    SensorId,
    load_reach_id_dosimeter_relationship,
)
from swxsoc_reach.util.schema import REACHDataSchema
from swxsoc_reach.util.util import get_reachid_lut

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


def impute_sensor_metadata(data: pd.DataFrame) -> pd.DataFrame:
    """
    Impute missing sensor IDs from the REACH lookup table and drop unresolved rows.

    Parameters
    ----------
    data : pd.DataFrame
        DataFrame with potential missing values in ``idSensor``.

    Returns
    -------
    pd.DataFrame
        DataFrame with missing ``idSensor`` values imputed where possible.
        Rows that still have missing ``idSensor`` values after imputation are
        removed and the index is reset.
    """
    reachids = get_reachid_lut()
    before = len(data)

    # Apply the Lookup Table to Impute Missing idSensor Values
    def impute_id_sensor(row):
        if pd.isna(row["idSensor"]):
            obs_name = row["observatoryName"]
            if obs_name in reachids:
                return reachids[obs_name]["reachid"]
        return row["idSensor"]

    data["idSensor"] = data.apply(impute_id_sensor, axis=1)
    data = data.dropna(subset=["idSensor"]).reset_index(drop=True)

    dropped = before - len(data)
    if dropped > 0:
        log.warning("Dropped %d rows with unresolved sensor metadata", dropped)

    return data


def extract_sensor_metadata() -> tuple[list[str], list[list[str | None]]]:
    """
    Extract canonical sensor IDs and per-sensor dosimeter flavor slots.

    Returns
    -------
    sensor_ids : list[str]
        Canonical list of all REACH sensor IDs in ``SensorId.to_index()`` order.
    observation_flavors : list[list[str | None]]
        For each sensor (matching ``sensor_ids`` order), a list of the
        canonical dosimeter flavor strings in fixed slot order, padded to
        exactly two slots per sensor.
    """
    sensor_ids = [str(sensor) for sensor in SensorId if sensor is not SensorId.ALL]
    relationship = load_reach_id_dosimeter_relationship()

    observation_flavors = []
    for sensor_id in sensor_ids:
        sensor_enum = SensorId.from_str(sensor_id)
        flavors = relationship.get(sensor_enum, ())
        labels = [f"Flavor {flavor.name}" for flavor in flavors[:2]]
        labels.extend([""] * (2 - len(labels)))
        observation_flavors.append(labels)

    log.info(
        "Found %d sensors, flavors per sensor: %s",
        len(sensor_ids),
        [len(f) for f in observation_flavors],
    )
    return sensor_ids, observation_flavors


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
        canonical dosimeter flavor strings in fixed slot order, padded to
        exactly two slots per sensor.

    Returns
    -------
    np.ndarray
        3-D float array of shape ``(n_times, n_sensors, 2)`` with NaN for
        missing values.
    """
    n_times = len(times_pd)
    n_sensors = len(sensor_ids)
    n_flavors = len(observation_flavors[0])

    dose_rate = np.full((n_times, n_sensors, n_flavors), np.nan, dtype=float)

    sensor_to_index = {sensor: idx for idx, sensor in enumerate(sensor_ids)}
    slot_lookup: dict[str, dict[Flavor, int]] = {}
    for sensor_idx, sensor in enumerate(sensor_ids):
        flavor_slots: dict[Flavor, int] = {}
        for slot_idx, flavor_label in enumerate(observation_flavors[sensor_idx]):
            if not flavor_label:
                continue
            flavor_slots[Flavor.from_str(flavor_label)] = slot_idx
        slot_lookup[sensor] = flavor_slots

    time_lookup = pd.Series(np.arange(n_times), index=times_pd)
    row_times = pd.to_datetime(data["obTime"].astype(str), utc=True)
    row_time_indices = time_lookup.reindex(row_times).to_numpy()

    row_sensors = data["idSensor"].astype(str).to_numpy()
    row_descriptions = data["obDescription"].astype(str).to_numpy()
    row_values = pd.to_numeric(data["obValue"], errors="coerce").to_numpy()

    for i, sensor in enumerate(row_sensors):
        if pd.isna(row_time_indices[i]):
            continue
        sensor_idx = sensor_to_index.get(sensor)
        if sensor_idx is None:
            continue

        match = re.search(
            r"\bflavor\s+([A-Za-z])\b", row_descriptions[i], flags=re.IGNORECASE
        )
        flavor_token = match.group(1) if match else row_descriptions[i]

        try:
            flavor = Flavor.from_str(flavor_token)
        except ValueError:
            continue

        slot_idx = slot_lookup[sensor].get(flavor)
        if slot_idx is None:
            continue

        dose_rate[int(row_time_indices[i]), sensor_idx, slot_idx] = row_values[i]

    return dose_rate


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
            s = pd.Series(
                dtype=float,
                index=pd.DatetimeIndex([]).tz_localize("UTC"),
                name=sensor,
            )
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
    2. **Extract canonical sensor metadata** (all sensor IDs and fixed
       two-slot dosimeter flavor layout)
       via :func:`extract_sensor_metadata`.
    3. **Build common time axis** from the unique UTC observation timestamps,
       stripping any trailing ``Z`` before parsing to avoid a stack overflow
       in astropy's recursive ISO-8601 parser for large arrays.
    4. **Pre-compute per-sensor groupby** on a sensor-deduplicated view of
       the data for efficient scalar-column extraction.
    5. **Build variable dict** of :class:`~astropy.nddata.NDData` arrays
         (dose-rate cube, geolocation/quality arrays, sensor-position arrays,
         and label/ID metadata variables).
    6. **Seed global attributes** from :class:`~swxsoc_reach.util.schema.REACHDataSchema`
       defaults, then overlay *version* and any caller-supplied *global_attrs*.
    7. **Assemble and return** a :class:`~swxsoc.swxdata.SWXData` instance
       ready to be written to CDF.

    The returned :class:`~swxsoc.swxdata.SWXData` contains:

    ===========================  ==========================================
    Variable                     Shape
    ===========================  ==========================================
    ``Epoch``                    ``(n_times,)``
    ``sensor_labels``            ``(32,)``
    ``sensor_ids``               ``(32,)``
    ``dosimeter_flavor_labels``  ``(2,)``
    ``dosimeter_flavor_ids``     ``(2,)``
    ``dosimeter_flavors``        ``(32, 2)``
    ``dose_rate``                ``(n_times, 32, 2)``
    ``lat``                      ``(n_times, 32)``
    ``lon``                      ``(n_times, 32)``
    ``alt``                      ``(n_times, 32)``
    ``obQuality``                ``(n_times, 32)``
    ``sensor_position_x``        ``(n_times, 32)``
    ``sensor_position_y``        ``(n_times, 32)``
    ``sensor_position_z``        ``(n_times, 32)``
    ===========================  ==========================================

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
    # --- 0.5 Fix and drop NaNs in Sensor Metadata ----------------------------------------
    data = impute_sensor_metadata(data)

    # --- 1. Deduplicate ------------------------------------------------
    data = deduplicate_records(data)

    # --- 2. Sensor metadata --------------------------------------------
    sensor_labels, observation_flavors = extract_sensor_metadata()

    # Convert Sensor Labels to pure numeric IDs if they follow the "REACH-XXX" pattern
    sensor_ids = np.asanyarray(
        [int(sensor.replace("REACH-", "").strip()) for sensor in sensor_labels],
        dtype=np.int32,
    )

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
    sensor_deduped_dt = pd.to_datetime(sensor_deduped["obTime"].astype(str), utc=True)
    sensor_grouped = sensor_deduped.groupby("idSensor")

    # --- 5. Build variable dict ----------------------------------------
    variables: dict[str, NDData] = {
        "sensor_labels": NDData(
            data=sensor_labels,
            meta={"CATDESC": "REACH Sensor Labels", "VAR_TYPE": "metadata"},
        ),
        "sensor_ids": NDData(
            data=sensor_ids,
            meta={"CATDESC": "REACH Sensor IDs", "VAR_TYPE": "metadata"},
        ),
        "dosimeter_flavor_labels": NDData(
            data=np.array(
                [f"flavor_{i}" for i in range(len(observation_flavors[0]))]
            ),  # Canonical two-slot flavor axis shared across all sensors
            meta={
                "CATDESC": "Label for dosimeter flavors dimension",
                "VAR_TYPE": "metadata",
                "VAR_NOTES": "Variable is just used for Label Pointer. For actual flavor strings, see 'dosimeter_flavors' variable.",
            },
        ),
        "dosimeter_flavor_ids": NDData(
            data=np.array(
                [i for i in range(len(observation_flavors[0]))], dtype=np.int32
            ),  # Canonical two-slot flavor axis shared across all sensors
            meta={
                "CATDESC": "ID for dosimeter flavors dimension",
                "VAR_TYPE": "metadata",
                "VAR_NOTES": "Variable is just used for DEPENDS. For actual flavor strings, see 'dosimeter_flavors' variable.",
            },
        ),
        "dosimeter_flavors": NDData(
            data=np.array(observation_flavors),
            meta={
                "CATDESC": "Observation Flavors per Sensor",
                "VAR_TYPE": "metadata",
            },
        ),
        "dose_rate": NDData(
            data=create_observation_array(
                data, sensor_labels, times_pd, observation_flavors
            ),
            meta={
                "CATDESC": "Dose rate for combined sensors and dosimeter flavors",
                "VAR_TYPE": "data",
                "UNITS": (u.J / u.kg * 0.01).to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "DEPEND_2": "dosimeter_flavor_ids",
                "LABL_PTR_1": "sensor_labels",
                "LABL_PTR_2": "dosimeter_flavor_labels",
            },
        ),
        "lat": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_labels, times_pd, "lat"
            ),
            meta={
                "CATDESC": "Latitude",
                "VAR_TYPE": "data",
                "UNITS": u.degree.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
            },
        ),
        "lon": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_labels, times_pd, "lon"
            ),
            meta={
                "CATDESC": "Longitude",
                "VAR_TYPE": "data",
                "UNITS": u.degree.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
            },
        ),
        "alt": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_labels, times_pd, "alt"
            ),
            meta={
                "CATDESC": "Altitude",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
            },
        ),
        "obQuality": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_labels, times_pd, "obQuality"
            ),
            meta={
                "CATDESC": "Observation Quality",
                "VAR_TYPE": "data",
                "UNITS": "unitless",
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
            },
        ),
        "sensor_position_x": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_labels, times_pd, "senPos0"
            ),
            meta={
                "CATDESC": "GEI Coordinate Position X in KM",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
            },
        ),
        "sensor_position_y": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_labels, times_pd, "senPos1"
            ),
            meta={
                "CATDESC": "GEI Coordinate Position Y in KM",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
            },
        ),
        "sensor_position_z": NDData(
            data=create_sensor_array(
                sensor_grouped, sensor_deduped_dt, sensor_labels, times_pd, "senPos2"
            ),
            meta={
                "CATDESC": "GEI Coordinate Position Z in KM",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
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

    # Determine whether PROVISIONAL or QUICKLOOK data based on descriptor
    if "descriptor" not in data.columns:
        raise ValueError(
            "Input data must contain a 'descriptor' column to determine data provenance."
        )
    # check that there is only one unique descriptor value
    unique_descriptors = data["descriptor"].unique()
    if len(unique_descriptors) > 1:
        raise ValueError(
            f"Expected only one unique descriptor value to determine data provenance, but found multiple: {unique_descriptors}"
        )
    descriptor = unique_descriptors[0]
    # Set Global Provenance based on descriptor content
    meta["UDL_Source"] = descriptor

    # --- 7. Assemble SWXData -------------------------------------------
    reach_data = SWXData(timeseries=ts, support=variables, meta=meta, schema=schema)

    log.info(
        "Built SWXData: %d time steps, %d sensors, %d support variables",
        len(ts),
        len(sensor_labels),
        len(variables),
    )
    return reach_data
