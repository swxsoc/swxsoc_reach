from astropy.time import Time
from swxsoc.util.util import parse_science_filename, TIME_FORMAT

__all__ = [
    "create_reach_filename",
    "parse_science_filename",
    "TIME_FORMAT",
]


def create_reach_filename(
    time: str,
    level: str,
    version: str,
    mode: str = "",
    descriptor: str = "",
):
    """
    Generate the REACH filename based on the provided parameters.

    Parameters
    ----------
    time : str
        The time associated with the data.
    level : str
        The data level (e.g., "L1", "L2").
    version : str
        The version string (e.g., "0.0.1"). This should be in the format major.minor.patch.
        This should come from the global attribute `Data_version`.
    mode : str
        The instrument mode (e.g., "all"). This should come from the global attribute `Instrument_mode`.
    descriptor : str
        The dataset descriptor (e.g., "prelim"). This should come from the global attribute `Data_type`.

    Returns
    -------
    str
        The generated REACH filename.
    """
    # Define Static Parts
    instrument_shortname = "reach"

    # Format Time String
    start_time = Time(time, format="isot")
    time_str = start_time.strftime(TIME_FORMAT)

    # Combine Parts into Filename
    filename = (
        f"{instrument_shortname}_{mode}_{level}_{descriptor}_{time_str}_v{version}.cdf"
    )
    filename = filename.replace("__", "_")  # reformat if mode or descriptor not given

    return filename
