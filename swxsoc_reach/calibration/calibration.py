"""
Pipeline entry point for processing REACH UDL files into CDF.
"""

import os
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
from swxsoc.util.validation import validate

from swxsoc_reach import log
from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.io.file_tools import read_file
from swxsoc_reach.track.trackbase import REACHTrack
from swxsoc_reach.util.enums import Flavor
from swxsoc_reach.util.schema import REACHDataSchema

__all__ = [
    "process_file",
]


def process_file(
    filename: Path,
) -> list[Path]:
    """
    Process a REACH data file from one data level to the next (e.g. UDL file to an ISTP-compliant CDF).

    For UDL files, reads the file, transforms the data into an
    :class:`~swxsoc.swxdata.SWXData` object, writes a CDF file, and
    runs ISTP validation (logging warnings on any issues without raising).

    For existing CDF files, creates one combined geomap CDF and JPG plots for
    all individual flavors (U, V, W, X, Y, Z).

    Parameters
    ----------
    filename : Path
        Path to the input UDL (JSON or CSV) file or existing CDF file.

    Returns
    -------
    list[Path]
        For UDL files: List containing the path to the output CDF file.
        For CDF files: List containing the original CDF file plus one geomap CDF
        and plot JPG files (one per flavor).
    """
    file_path = Path(filename)
    log.info(f"Processing file {file_path}.")

    # Stub Output Files
    output_files = []

    # Read and transform

    # *****************************
    # CHECK FILE TYPE; IF CDF THEN CREATE MAP CDF.

    if file_path.suffix.lower() == ".cdf":  # TODO also check that data level is l1c
        log.info("Input file is already a CDF. Creating geomap CDFs and plots.")
        try:
            track = REACHTrack.load(file_path)

            # Get metadata for filename generation
            version = track.meta.get("Data_version", "1.0.0")
            time_obj = track.time[0]  # Get first time from track
            time_str = time_obj.strftime("%Y%m%dT%H%M%S")  # Format as YYYYMMDDTHHMMSS

            # Check if the LAMBDA_ENVIRONMENT environment variable is set
            lambda_environment = os.getenv("LAMBDA_ENVIRONMENT")
            if lambda_environment:
                output_path = Path(tempfile.gettempdir())
            else:
                output_path = Path.cwd()  # Default to current working directory

            geomap = track.to_geomap()

            # Save the combined geomap once, then render one plot per flavor.
            geomap_cdf_path = geomap.save(
                output_path=output_path,
                overwrite=True,
            )
            log.info(f"Saved geomap CDF to {geomap_cdf_path}")
            output_files.append(geomap_cdf_path)

            # Iterate over all individual flavors (exclude ALL which is a combination)
            for flavor in Flavor:
                if flavor == Flavor.ALL:
                    continue
                try:
                    # Create and save plot as JPG
                    fig = plt.figure()
                    ax, mesh = geomap.plot(flavor=flavor)

                    plot_jpg_filename = file_path.stem + f"_geomap_{flavor.name}.jpg"
                    plot_jpg_path = output_path / plot_jpg_filename
                    fig.savefig(
                        str(plot_jpg_path), format="jpg", dpi=150, bbox_inches="tight"
                    )
                    plt.close(fig)
                    log.info(f"Saved geomap plot to {plot_jpg_path}")
                    output_files.append(plot_jpg_path)

                except ValueError as e:
                    log.warning(
                        f"Could not create geomap for flavor {flavor.name}: {e}"
                    )
                except Exception as e:
                    log.warning(f"Error creating geomap for flavor {flavor.name}: {e}")

        except Exception as e:
            log.warning(f"Could not create geomaps and plots: {e}")

        return output_files
    else:
        log.info("Input file is not a CDF. Processing as UDL file.")

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

    return output_files
