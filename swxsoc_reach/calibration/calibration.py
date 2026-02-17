"""
Pipeline entry point for processing REACH UDL files into CDF.
"""

from pathlib import Path

from swxsoc.util.validation import validate

from swxsoc_reach import log
from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.io.file_tools import read_udl_json

__all__ = [
    "process_file",
]


def process_file(
    filename: Path,
) -> list[Path]:
    """
    Process a REACH UDL JSON file into an ISTP-compliant CDF.

    Reads the JSON file, transforms the data into an
    :class:`~swxsoc.swxdata.SWXData` object, writes a CDF file, and
    runs ISTP validation (logging warnings on any issues without raising).

    Parameters
    ----------
    filename : Path
        Path to the input UDL JSON file.

    Returns
    -------
    list[Path]
        List containing the path to the output CDF file.
    """
    file_path = Path(filename)
    log.info(f"Processing file {file_path}.")

    # Save to the working directory
    output_path = Path.cwd()

    # Read and transform
    data = read_udl_json(file_path)
    reach_data = build_swxdata(data)

    # Write CDF
    cdf_path = reach_data.save(output_path=output_path, overwrite=True)
    log.info(f"Saved CDF to {cdf_path}")

    # Validate (warn only, do not raise)
    try:
        validation_errors = validate(cdf_path)
        if validation_errors:
            for err in validation_errors:
                log.warning(f"Validation issue: {err}")
    except Exception as exc:
        log.warning(f"Validation could not complete: {exc}")

    return [Path(cdf_path)]
