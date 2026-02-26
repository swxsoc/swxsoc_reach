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

__all__ = [
    "process_file",
]


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
