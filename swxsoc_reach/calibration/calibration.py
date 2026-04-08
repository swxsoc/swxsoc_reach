"""
Pipeline entry point for processing REACH UDL files into CDF.
"""

import os
from pathlib import Path
import tempfile

from swxsoc.util.validation import validate

from swxsoc_reach import log
from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.io.file_tools import read_file
from swxsoc_reach.util.schema import REACHDataSchema
from swxsoc_reach.swxdata import SWXData

__all__ = [
    "process_file",
]


def raw_to_mapdata(v: SWXData)-> SWXData:
    # take in raw data in SWXData format and transforms it in xylon, xylat gridded data and puts it into a new SWXData object.
    pass

def plot_mapdata(newv: SWXData, fileout: str)-> Path:
    # takes in newv which is the gridded data in SWXData format and makes the plot and saves to fileout.
    pass

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

#*****************************
#CHECK FILE TYPE; IF CDF THEN CREATE MAP CDF. 

    if file_path.suffix.lower() == ".cdf":
        log.info(f"Input file is already a CDF. Creating map CDF.")
        # Create map CDF (stubbed for now)
        v = SWXData(file_path) # read in the CDF file into a SWXData object (stubbed)
        gridded_data = raw_to_mapdata(v)
        gridded_file_path = "gridded_data.cdf"
        gridded_data.save(fileout=gridded_file_path, overwrite=True) # save the gridded data to a new CDF file (stubbed)
        output_files.append(file_path) # add the original CDF to the output files list
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
