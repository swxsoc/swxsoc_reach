"""
Pipeline entry point for processing REACH UDL files into CDF.
"""

import os
import tempfile
from pathlib import Path

import numpy as np
from swxsoc.swxdata import SWXData
from swxsoc.util.validation import validate

from swxsoc_reach import log
from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.io.file_tools import read_file
from swxsoc_reach.util.schema import REACHDataSchema
from swxsoc_reach.util.util import load_regions
from swxsoc_reach.visualization.viz import plot_mapdata

__all__ = [
    "process_file",
]


def raw_to_mapdata(v: SWXData) -> SWXData:
    # def raw_to_mapdata(v):
    # take in raw data in SWXData format and transforms it to gridded data for plotting

    lat = v["lat"].data
    lon = v["lon"].data
    Epoch = v["time"]
    tst = v["observations"].data  # [ntimes, nsats, ndos]
    dosA = tst[:, :, 0]
    dosB = tst[:, :, 1]
    # dosC = tst[:, :, 2] if tst.shape[2] > 2 else None

    pltdos = "dA"
    if pltdos == "dA":
        dos = dosA
    else:
        dos = dosB

    n_times, n_sats = dos.shape

    lookuplon, lookuplat, glook = load_regions()

    # Create 2D region grid
    region_grid = np.zeros((360, 180), dtype=int)
    lon_indices = ((lookuplon + 180) % 360).astype(int)
    lat_indices = (lookuplat + 90).astype(int)
    region_grid[lon_indices, lat_indices] = glook

    # Grid the data using vectorized operations
    # Initialize as lists to collect all values per bin
    dos_bins = [[[] for _ in range(180)] for _ in range(360)]

    for t in range(n_times):
        for s in range(n_sats):
            dos_val = dos[t, s]
            lat_val = lat[t, s]
            lon_val = lon[t, s]
            if not np.isnan(lat_val) and not np.isnan(lon_val):  # Allow nans in dos
                # Convert to grid indices
                lon_idx = int((lon_val + 180) % 360)
                lat_idx = int(lat_val + 90)

                # Ensure indices are within bounds
                if 0 <= lon_idx < 360 and 0 <= lat_idx < 180:
                    dos_bins[lon_idx][lat_idx].append(dos_val)

    # Compute medians
    gridded_dos = np.zeros((360, 180)) * np.nan
    for i in range(360):
        for j in range(180):
            if dos_bins[i][j]:
                gridded_dos[i, j] = np.nanmedian(dos_bins[i][j])

    # Assign to regions using masks
    SAA = np.zeros((360, 180)) * np.nan
    PC = np.zeros((360, 180)) * np.nan
    outrad = np.zeros((360, 180)) * np.nan
    slot = np.zeros((360, 180)) * np.nan

    saa_mask = (region_grid == 1) | (region_grid == -1)
    pc_mask = (region_grid == 2) | (region_grid == -2)
    outrad_mask = (region_grid == 3) | (region_grid == -3)
    slot_mask = (region_grid == 4) | (region_grid == -4)

    SAA[saa_mask] = gridded_dos[saa_mask]
    PC[pc_mask] = gridded_dos[pc_mask]
    outrad[outrad_mask] = gridded_dos[outrad_mask]
    slot[slot_mask] = gridded_dos[slot_mask]

    # Set inf and limiting values to nan
    for arr in [SAA, PC, outrad, slot]:
        badinf = np.where(np.isinf(arr))
        arr[badinf] = np.nan
        # Also set very large values to nan (assuming limiting is >1e30)
        large_vals = np.where(np.abs(arr) > 1e30)
        arr[large_vals] = np.nan

    # Create coordinate grids
    lon_bins = np.arange(-180, 180, 1) + 0.5  # bin centers
    lat_bins = np.arange(-90, 90, 1) + 0.5
    xylon, xylat = np.meshgrid(lon_bins, lat_bins)

    plotTitlePre = str(
        np.min(Epoch).strftime("%d %b %Y %H:%M")
        + " - "
        + np.max(Epoch).strftime("%d %b %Y %H:%M")
    )

    if len(Epoch) < 1:
        dataToPlot = 0
    else:
        dataToPlot = 1

    newv = {
        "xylon": np.transpose(xylon),
        "xylat": np.transpose(xylat),
        "SAA": SAA,
        "PC": PC,
        "outrad": outrad,
        "slot": slot,
        "plotTitlePre": plotTitlePre,
        "dataToPlot": dataToPlot,
        "pltdos": pltdos,
    }  # TODO should load into a SWXData object instead

    return newv


def process_file(
    filename: Path,
) -> list[Path]:
    """
    Process a REACH data file from one data level to the next (e.g. UDL file to an ISTP-compliant CDF).

    Reads the file, transforms the data into an
    :class:`~swxsoc.swxdata.SWXData` object, writes a CDF file, and
    runs ISTP validation (logging warnings on any issues without raising).

    Parameters
    ----------
    filename : Path
        Path to the input UDL (JSON or CSV) file.

    Returns
    -------
    list[Path]
        List containing the path to the output CDF file.
    """
    file_path = Path(filename)
    log.info(f"Processing file {file_path}.")

    # Stub Output Files
    output_files = []

    # Read and transform

    # *****************************
    # CHECK FILE TYPE; IF CDF THEN CREATE MAP CDF.

    if file_path.suffix.lower() == ".cdf":  # TODO also check that data level is l1c
        log.info(f"Input file is already a CDF. Creating map CDF.")
        # Create map CDF (stubbed for now)
        v = SWXData(file_path)  # read in the CDF file into a SWXData object (stubbed)
        gridded_data = raw_to_mapdata(v)
        gridded_file_path = "gridded_data.cdf"
        gridded_data.save(
            fileout=gridded_file_path, overwrite=True
        )  # save the gridded data to a new CDF file (stubbed)
        output_files.append(file_path)  # add the original CDF to the output files list
        map_cdf_path = plot_mapdata(gridded_data, fileout="map_cdf_output.png")
        output_files.append(map_cdf_path)
        return output_files
    else:
        log.info(f"Input file is not a CDF. Processing as UDL file.")

        data = read_file(file_path)
        reach_data = build_swxdata(data)

        # Check if the LAMBDA_ENVIRONMENT environment variable is set
        lambda_environment = os.getenv("LAMBDA_ENVIRONMENT")
        if lambda_environment:
            output_path = Path(tempfile.gettempdir())
        else:
            output_path = Path.cwd()  # Default to current working directory
        # Write CDF
        cdf_path = reach_data.save(output_path=output_path, overwrite=True)
        log.info(f"Saved CDF to {cdf_path}")
        output_files.append(cdf_path)

        # Validate (warn only, do not raise)
        schema = REACHDataSchema()
        try:
            validation_errors = validate(cdf_path, schema=schema)
            if validation_errors:
                for err in validation_errors:
                    log.warning(f"Validation issue: {err}")
        except Exception as exc:
            log.warning(f"Validation could not complete: {exc}")

        # NOTE: Can add additional processing steps here if needed and return multiple output files as needed.

    return output_files


cdf_test = Path(
    "/Users/abrenema/Desktop/code/Aaron/github/swxsoc_reach/swxsoc_reach/data/test/swxsoc_pipeline_reach_all_l1_prelim_20251201T000000_v1.0.0.cdf"
)
v = SWXData.load(cdf_test)
newv = raw_to_mapdata(v)

import os

home = os.environ["HOME"]
fileout = home + "/Desktop/test_grid.png"

plot_mapdata(newv=newv, fileout=fileout, flav="Z")


print("h")
