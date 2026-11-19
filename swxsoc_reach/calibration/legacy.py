"""
Processing of the Aerospace Corp. "Legacy" pipeline data into REACH CDF files.

The Legacy pipeline delivers one CSV per spacecraft per UTC day, with one row
per ``(time, spacecraft)`` and both dosimeters on the same row. This module
reshapes that data into the long UDL-shaped frame that
:func:`~swxsoc_reach.calibration.transform.build_swxdata` expects, adds the
variables that only exist in the Legacy pipeline, and writes the CDF.

The high-level entry point is :func:`process_legacy_day`.
"""

from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
import numpy as np
import pandas as pd
from astropy.nddata import NDData
from astropy.time import Time
from swxsoc.swxdata import SWXData
from swxsoc.util.validation import validate

from swxsoc_reach import log
from swxsoc_reach.calibration.transform import (
    build_swxdata,
    create_observation_array,
    create_sensor_array,
    deduplicate_records,
    extract_sensor_metadata,
    impute_sensor_metadata,
    replace_fill_values_with_nan,
)
from swxsoc_reach.io.file_tools import read_legacy_pipeline_day
from swxsoc_reach.util.enums import dosimeter_flavor
from swxsoc_reach.util.schema import REACHDataSchema
from swxsoc_reach.util.util import get_reachid_lut

__all__ = [
    "re_to_km",
    "legacy_to_udl_frame",
    "add_legacy_variables",
    "set_legacy_global_attributes",
    "process_legacy_day",
]

# Earth radius (km) used to convert GEI RE to km (TOR-2021-01076)
RE_KM = 6371.2

# Values at or below this threshold are FILLVAL markers (REACH uses -1e31).
_FILLVAL_THRESHOLD = -1e30


def re_to_km(values: pd.Series) -> np.ndarray:
    """
    Scale Earth-radius values to km, keeping fill values unchanged.

    Parameters
    ----------
    values : pd.Series
        Values in units of Earth radii (RE). Entries at or below ``-1e30``
        are treated as fill values.

    Returns
    -------
    np.ndarray
        Values in km, with fill values left as delivered.
    """
    values = values.to_numpy(dtype=float)
    return np.where(values <= _FILLVAL_THRESHOLD, values, values * RE_KM)


def masked_int8_ndata(values: np.ndarray, meta: dict) -> NDData:
    """
    Wrap a float array (NaN = missing) as an int8 NDData whose missing values are masked.

    Parameters
    ----------
    values : np.ndarray
        Array of float values, with NaN indicating missing data.
    meta : dict
        Metadata dictionary to attach to the NDData object.

    Returns
    -------
    NDData
        An NDData object containing the int8 data and a mask for missing values.
    """
    mask = np.isnan(values)
    return NDData(data=np.where(mask, 0, values).astype(np.int8), mask=mask, meta=meta)


def legacy_to_udl_frame(df: pd.DataFrame, descriptor: str = "LEGACY") -> pd.DataFrame:
    """
    Reshape Legacy rows (one per VID and time, two dosimeters) into the long UDL-shaped frame for ``build_swxdata()``.

    We want to piggy-back on the existing ``build_swxdata()`` function for UDL
    data so we can ensure compatibility between the UDL derived data and the
    Legacy pipeline derived data.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing Legacy pipeline data for a single day, as returned
        by :func:`~swxsoc_reach.io.file_tools.read_legacy_pipeline_day`.
    descriptor : str, optional
        Descriptor to use for the ``descriptor`` column in the output
        DataFrame. Default is ``"LEGACY"``.

    Returns
    -------
    pd.DataFrame
        Long DataFrame with one row per ``(time, spacecraft, dosimeter)``.
    """
    # Mapper from REACH-ID to Iridium Observatory Name for the 'observatoryName' column.
    reach_to_iridium = {
        info["reachid"]: name for name, info in get_reachid_lut().items()
    }

    # Parse out REACH-ID to match expected format.
    sensor: pd.Series = "REACH-" + df["VID"].astype(str)
    # Convert obTime to ISO-format with milliseconds and Z suffix for UTC.
    obtime = df["obTime"].dt.strftime("%Y-%m-%dT%H:%M:%S.%f").str[:-3] + "Z"

    # UDL had Duplicate obTime and idSensor keys, differentiated by a "createdAt" column.
    # We de-duplicated the UDL data taking the last "createdAt" value for each (obTime, idSensor) pair.
    # See swxsoc_reach.calibration.transform.deduplicate_records for more details
    # We just create the column for the Legacy data to match the UDL data,
    # but we don't need to de-duplicate since the Legacy data is already unique.
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # fmt: off
    base = pd.DataFrame(
        {
            "obTime": obtime.to_numpy(),                                    # string UTC ISO Time: e.g. "2026-08-01T00:00:00.000Z"
            "idSensor": sensor.to_numpy(),                                  # REACH-ID: e.g. "REACH-101"
            "observatoryName": sensor.map(reach_to_iridium).to_numpy(),     # e.g. "IRIDIUM-101"
            "lat": df["LAT deg"].to_numpy(),
            "lon": df["LON deg"].to_numpy(),
            "alt": df["ALT km"].to_numpy(),
            "obQuality": df["Flag"].to_numpy(),
            "senPos0": re_to_km(df["GEI_X RE"]),                            # Upstream Plotting tools expect GEI Coords
            "senPos1": re_to_km(df["GEI_Y RE"]),                            # to be in km, not RE. See TOR-2021-01076 for details.
            "senPos2": re_to_km(df["GEI_Z RE"]),
            "createdAt": created_at,
            "descriptor": descriptor,
            "source_file": df["source_file"].to_numpy(),                    # Carry forward the source file name for traceability / provenance
            # The Following are "Legacy" Pipeline *Unique* columns that we pass through to the UDL frame for additional variables
            # ======================================================== | Data Type | Units | Description
            "hk_temperature": df["HK Temperature deg C"].to_numpy(), # | float64   | deg C | Housekeeping Temperature
            "hk_15v_monitor": df["HK 15V Monitor"].to_numpy(),       # | float64   | V     | Housekeeping 15V Monitor
            "hk_5v_monitor": df["HK 5V Monitor"].to_numpy(),         # | float64   | V     | Housekeeping 5V Monitor
            "hk_3_3v_monitor": df["HK 3.3V Monitor"].to_numpy(),     # | float64   | V     | Housekeeping 3.3V Monitor
            "lm": df["Lm RE"].to_numpy(),                            # | float64   | RE    | McIlwain L-shell for locally mirroring particle
            "inv_lat": df["Inv_Lat deg"].to_numpy(),                 # | float64   | deg   | Invariant Latitude for locally mirroring particle
            "blocal": df["Blocal nT"].to_numpy(),                    # | float64   | nT    | Local Magnetic Field Strength at S/C
            "bmin": df["Bmin nT"].to_numpy(),                        # | float64   | nT    | Minimum magnetic field on field line intersecting spacecraft
            "mlt": df["MLT hr"].to_numpy(),                          # | float64   | hr    | Magnetic Local Time (MLT) of spacecraft
            "k_sqrt": df["K sqrt(G)RE"].to_numpy(),                  # | float64   | RE    | Kaufmann's modified bounce invariant
            "hmin": df["hmin km"].to_numpy(),                        # | float64   | km    | The minimum mirror altitude around the drift shell for a locally mirroring particle.
            "alpha": df["Alpha deg"].to_numpy(),                     # | float64   | deg   | Local pitch angle
            "alpha_eq": df["Alpha Eq deg"].to_numpy(),               # | float64   | deg   | Equatorial pitch angle
            "region_code": df["Region Code"].to_numpy(),             # | int64     |       | Region code
            "orbit_status": df["Orbit Status"].to_numpy(),           # | int64     |       | Orbit status Northbound/ Southbound (NOBO=0, SOBO=1)
        }
    )
    # fmt: on

    frames = []
    for slot in range(2):
        # Columns we want to extract for this dosimeter slot
        # Carry-over from the UDL data, although they just call it "obValue" in the UDL data
        dose_col = f"DOSE{slot + 1} rad/s"
        # New in the "Legacy" Pipeline data
        prot_flux_col = f"PROT FLUX{slot + 1} #/cm^2/sr/s"
        elec_flux_col = f"ELEC FLUX{slot + 1} #/cm^2/sr/s"
        species_col = f"SPECIES{slot + 1}"

        flavor_text = {
            s: f"DOSE{slot + 1} (Flavor {dosimeter_flavor(s, slot)}) in rad/second"
            for s in sensor.unique()
        }
        part = base.copy()
        # Add a Description Column to pass forward the Flavor Text for each REACH-ID and Dosimeter Slot
        part["obDescription"] = sensor.map(flavor_text).to_numpy()

        # Measurements for this dosimeter slot
        part["obValue"] = df[dose_col].to_numpy()
        part["protFlux"] = df[prot_flux_col].to_numpy()
        part["elecFlux"] = df[elec_flux_col].to_numpy()
        part["species"] = df[species_col].to_numpy()
        frames.append(part)

    frame = pd.concat(frames, ignore_index=True)
    return frame.sort_values(["obTime", "idSensor", "obDescription"], ignore_index=True)


def add_legacy_variables(reach_data: SWXData, udl_frame: pd.DataFrame) -> None:
    """
    Add the Legacy-pipeline-only variables to a ``build_swxdata()`` result.

    ``build_swxdata()`` only knows about the UDL variable set. The Legacy
    columns that have no UDL equivalent are added here with
    :meth:`~swxsoc.swxdata.SWXData.add_support`, since they are
    ``(n_times, n_sensors)`` or ``(n_times, n_sensors, 2)`` arrays indexed by
    IDs rather than by a WCS.

    The same preprocessing (fill to NaN, sensor imputation, de-duplication)
    and the same sensor/flavor/time layout as ``build_swxdata()`` is used so
    every new array lines up with ``Epoch``, ``sensor_ids`` and
    ``dosimeter_flavor_ids``.

    Parameters
    ----------
    reach_data : SWXData
        Object returned by ``build_swxdata(udl_frame)``. Modified in place.
    udl_frame : pd.DataFrame
        The frame produced by :func:`legacy_to_udl_frame` that was passed to
        ``build_swxdata()``.

    Raises
    ------
    ValueError
        If the time axis derived here does not match ``reach_data``.
    """
    # Replicate the build_swxdata() preprocessing so the new arrays share its exact axes.
    data = replace_fill_values_with_nan(udl_frame.copy())
    data = impute_sensor_metadata(data)
    data = deduplicate_records(data)

    sensor_labels, observation_flavors = extract_sensor_metadata()
    times_pd = pd.DatetimeIndex(
        pd.to_datetime(sorted(data["obTime"].unique()), utc=True)
    )
    if len(times_pd) != len(reach_data.timeseries):
        raise ValueError(
            f"Time axis mismatch with reach_data: {len(times_pd)} vs "
            f"{len(reach_data.timeseries)} time steps."
        )

    sensor_deduped = data.drop_duplicates(subset=["idSensor", "obTime"], keep="first")
    sensor_deduped_dt = pd.to_datetime(sensor_deduped["obTime"].astype(str), utc=True)
    sensor_grouped = sensor_deduped.groupby("idSensor")

    # Descriptions follow TOR-2021-01076 Table 6 (REACH Level 1B Data Dictionary).

    # --- Housekeeping -------------------------------------------------------------
    reach_data.add_support(
        "hk_temperature",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="hk_temperature",
                dtype=np.float32,
            ),
            meta={
                "CATDESC": "Housekeeping Temperature",
                "VAR_TYPE": "data",
                "UNITS": u.deg_C.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 40.0,
            },
        ),
    )

    reach_data.add_support(
        "hk_15v_monitor",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="hk_15v_monitor",
                dtype=np.float32,
            ),
            meta={
                "CATDESC": "Housekeeping 15V Monitor",
                "VAR_TYPE": "data",
                "UNITS": u.V.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 30.0,
            },
        ),
    )

    reach_data.add_support(
        "hk_5v_monitor",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="hk_5v_monitor",
                dtype=np.float32,
            ),
            meta={
                "CATDESC": "Housekeeping 5V Monitor",
                "VAR_TYPE": "data",
                "UNITS": u.V.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 15.0,
            },
        ),
    )

    reach_data.add_support(
        "hk_3_3v_monitor",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="hk_3_3v_monitor",
                dtype=np.float32,
            ),
            meta={
                "CATDESC": "Housekeeping 3.3V Monitor",
                "VAR_TYPE": "data",
                "UNITS": u.V.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 7.0,
            },
        ),
    )

    # --- Magnetic coordinates / field ---------------------------------------------
    reach_data.add_support(
        "lm",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="lm",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "McIlwain L-shell for locally mirroring particle",
                "VAR_TYPE": "data",
                "UNITS": u.R_earth.to_string(),
                "VAR_NOTES": "Computed with IGRF. Earth radius RE = 6371.2 km.",
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 30.0,
            },
        ),
    )

    reach_data.add_support(
        "inv_lat",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="inv_lat",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Invariant Latitude for locally mirroring particle",
                "VAR_TYPE": "data",
                "UNITS": u.degree.to_string(),
                "VAR_NOTES": "cos^2(inv_lat) = 1/Lm.",
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": -90.0,
                "VALIDMAX": 90.0,
            },
        ),
    )

    reach_data.add_support(
        "blocal",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="blocal",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Local Magnetic Field Strength at spacecraft",
                "VAR_TYPE": "data",
                "UNITS": u.nT.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 50000.0,
            },
        ),
    )

    reach_data.add_support(
        "bmin",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="bmin",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Minimum magnetic field on field line intersecting spacecraft",
                "VAR_TYPE": "data",
                "UNITS": u.nT.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 30000.0,
            },
        ),
    )

    reach_data.add_support(
        "mlt",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="mlt",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Magnetic Local Time",
                "VAR_TYPE": "data",
                "UNITS": u.hour.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 24.0,
            },
        ),
    )

    reach_data.add_support(
        "k_sqrt",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="k_sqrt",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Kaufmann's modified bounce invariant",
                "VAR_TYPE": "data",
                "UNITS": u.R_earth.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 20000.0,
            },
        ),
    )

    reach_data.add_support(
        "hmin",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="hmin",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Minimum mirror altitude around the drift shell for a locally mirroring particle",
                "VAR_TYPE": "data",
                "UNITS": u.km.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": -3000.0,
                "VALIDMAX": 1000.0,
            },
        ),
    )

    reach_data.add_support(
        "alpha",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="alpha",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Local pitch angle",
                "VAR_TYPE": "data",
                "UNITS": u.degree.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 180.0,
            },
        ),
    )

    reach_data.add_support(
        "alpha_eq",
        NDData(
            data=create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="alpha_eq",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Equatorial pitch angle",
                "VAR_TYPE": "data",
                "UNITS": u.degree.to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 90.0,
            },
        ),
    )

    # --- Categorical per-sensor codes (int8, missing values masked) ---------------
    reach_data.add_support(
        "region_code",
        masked_int8_ndata(
            create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="region_code",
            ),
            meta={
                "CATDESC": "REACH magnetospheric region code",
                "VAR_TYPE": "data",
                "UNITS": "unitless",
                "VAR_NOTES": (
                    "-4: Southern polar cap, -3: Outer zone untrapped, -2: Slot untrapped, "
                    "-1: Inner zone untrapped, 0: Unknown, +1: Inner zone trapped, "
                    "+2: Slot trapped, +3: Outer zone trapped, +4: Northern polar cap. "
                    "See TOR-2021-01076 Table 4."
                ),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": -4,
                "VALIDMAX": 4,
            },
        ),
    )

    reach_data.add_support(
        "orbit_status",
        masked_int8_ndata(
            create_sensor_array(
                sensor_grouped=sensor_grouped,
                sensor_deduped_dt=sensor_deduped_dt,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                col="orbit_status",
            ),
            meta={
                "CATDESC": "Orbit status (northbound or southbound)",
                "VAR_TYPE": "data",
                "UNITS": "unitless",
                "VAR_NOTES": "0: Northbound (NOBO), 1: Southbound (SOBO).",
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "LABL_PTR_1": "sensor_labels",
                "VALIDMIN": 0,
                "VALIDMAX": 1,
            },
        ),
    )

    # --- Per-sensor, per-dosimeter-slot variables (n_times, 32, 2) ----------------
    reach_data.add_support(
        "proton_flux",
        NDData(
            data=create_observation_array(
                data=data,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                observation_flavors=observation_flavors,
                observation_col="protFlux",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Proton flux from bowtie analysis for combined sensors and dosimeter flavors",
                "VAR_TYPE": "data",
                "UNITS": u.Unit("cm-2 sr-1 s-1").to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "DEPEND_2": "dosimeter_flavor_ids",
                "LABL_PTR_1": "sensor_labels",
                "LABL_PTR_2": "dosimeter_flavor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 10000000.0,
                "SCALETYP": "log",
            },
        ),
    )

    reach_data.add_support(
        "electron_flux",
        NDData(
            data=create_observation_array(
                data=data,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                observation_flavors=observation_flavors,
                observation_col="elecFlux",
                dtype=np.float64,
            ),
            meta={
                "CATDESC": "Electron flux from bowtie analysis for combined sensors and dosimeter flavors",
                "VAR_TYPE": "data",
                "UNITS": u.Unit("cm-2 sr-1 s-1").to_string(),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "DEPEND_2": "dosimeter_flavor_ids",
                "LABL_PTR_1": "sensor_labels",
                "LABL_PTR_2": "dosimeter_flavor_labels",
                "VALIDMIN": 0.0,
                "VALIDMAX": 1000000000.0,
                "SCALETYP": "log",
            },
        ),
    )

    reach_data.add_support(
        "species",
        masked_int8_ndata(
            create_observation_array(
                data=data,
                sensor_ids=sensor_labels,
                times_pd=times_pd,
                observation_flavors=observation_flavors,
                observation_col="species",
            ),
            meta={
                "CATDESC": "Most probable species for combined sensors and dosimeter flavors",
                "VAR_TYPE": "data",
                "UNITS": "unitless",
                "VAR_NOTES": (
                    "0: Not currently used, 1: Protons, 2: Electrons, 3: Both / ambiguous. "
                    "See TOR-2021-01076 Section 2.7."
                ),
                "DEPEND_0": "Epoch",
                "DEPEND_1": "sensor_ids",
                "DEPEND_2": "dosimeter_flavor_ids",
                "LABL_PTR_1": "sensor_labels",
                "LABL_PTR_2": "dosimeter_flavor_labels",
                "VALIDMIN": 0,
                "VALIDMAX": 3,
            },
        ),
    )


def set_legacy_global_attributes(reach_data: SWXData) -> None:
    """Update the global metadata to reflect the Legacy pipeline source and cadence."""
    reach_data.meta["Data_level"] = "L1>Level 1"
    reach_data.meta["Data_type"] = "5s>5 Second Cadence"
    # Re-derive the dependent attributes (e.g. Logical_file_id) from the updated values.
    reach_data._derive_metadata()


def process_legacy_day(
    day: Time,
    data_dir: Path,
    output_dir: Path | None = None,
    version: str = "1.0.0",
) -> Path:
    """
    Process one UTC day of Legacy pipeline CSV files into a REACH CDF file.

    Runs the full pipeline: read the day's per-spacecraft CSV files, reshape
    them to the UDL layout, build the ``SWXData`` object, add the
    Legacy-only variables, update the global attributes, write the CDF, and
    run ISTP validation (logging warnings on any issues without raising).

    Parameters
    ----------
    day : Time
        The UTC day to process.
    data_dir : Path
        Directory containing the Legacy CSV files for the day
        (e.g. ``reach.20260801.vid-101.l1b.v3.csv``).
    output_dir : Path, optional
        Directory to write the CDF to. Defaults to the current working
        directory.
    version : str, optional
        Data version written into the ``Data_version`` global attribute
        (default ``"1.0.0"``).

    Returns
    -------
    Path
        Path to the written CDF file.

    Raises
    ------
    FileNotFoundError
        If no Legacy files are found for *day* in *data_dir*.
    ValueError
        If no readable Legacy files exist for *day*.
    """
    log.info(f"Processing Legacy pipeline data for {day.iso} from {data_dir}.")

    # Look for and read the Legacy CSV files for the day
    # returns a DataFrame with one row per (time, spacecraft) and all Legacy columns
    # Raises FileNotFoundError if no files are found, ValueError if no readable files exist
    df = read_legacy_pipeline_day(data_dir=Path(data_dir), day=day)

    # Reshape the Legacy DataFrame into the long UDL-shaped frame for build_swxdata()
    # Converts from one row per (time, spacecraft) with two dosimeters
    # to one row per (time, spacecraft, dosimeter)
    udl_frame = legacy_to_udl_frame(df)

    # Build the SWXData object from the UDL frame
    reach_data = build_swxdata(udl_frame, version=version)
    # Add the Legacy-only variables to the SWXData object
    add_legacy_variables(reach_data, udl_frame)
    # Update the global attributes to reflect the Legacy pipeline source and cadence
    set_legacy_global_attributes(reach_data)

    output_path = Path(output_dir) if output_dir is not None else Path.cwd()
    output_path.mkdir(parents=True, exist_ok=True)
    cdf_path = Path(reach_data.save(output_path=output_path, overwrite=True))
    log.info(f"Saved CDF to {cdf_path}")

    # Validate (warn only, do not raise)
    try:
        validation_errors = validate(cdf_path, schema=REACHDataSchema())
        for err in validation_errors:
            log.warning(f"Validation issue: {err}")
    except Exception as exc:
        log.warning(f"Validation could not complete: {exc}")

    return cdf_path
