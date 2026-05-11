from astropy.time import Time
from swxsoc.util.util import parse_science_filename, TIME_FORMAT

__all__ = [
    "create_reach_filename",
    "parse_science_filename",
    "TIME_FORMAT",
]


def get_reachid_lut():
    """
    Function to return a lookup table (dictionary) mapping Iridium satellite names to their corresponding REACH IDs and POD model numbers.

    Returns
    -------
    dict
        A dictionary where the keys are Iridium satellite names (e.g., 'Iridium-102') and the values are dictionaries containing 'reachid' and 'pod_model' keys with their corresponding values.
    """

    reachids = {
        "Iridium-102": {"reachid": "REACH-101", "pod_model": "1"},
        "Iridium-113": {"reachid": "REACH-102", "pod_model": "2"},
        "Iridium-106": {"reachid": "REACH-105", "pod_model": "3"},
        "Iridium-133": {"reachid": "REACH-108", "pod_model": "1"},
        "Iridium-121": {"reachid": "REACH-113", "pod_model": "2"},
        "Iridium-110": {"reachid": "REACH-114", "pod_model": "1"},
        "Iridium-107": {"reachid": "REACH-115", "pod_model": "1"},
        "Iridium-108": {"reachid": "REACH-116", "pod_model": "2"},
        "Iridium-117": {"reachid": "REACH-133", "pod_model": "1"},
        "Iridium-125": {"reachid": "REACH-134", "pod_model": "3"},
        "Iridium-126": {"reachid": "REACH-135", "pod_model": "1"},
        "Iridium-132": {"reachid": "REACH-136", "pod_model": "1"},
        "Iridium-119": {"reachid": "REACH-137", "pod_model": "1"},
        "Iridium-134": {"reachid": "REACH-138", "pod_model": "3"},
        "Iridium-137": {"reachid": "REACH-139", "pod_model": "1"},
        "Iridium-122": {"reachid": "REACH-140", "pod_model": "2"},
        "Iridium-131": {"reachid": "REACH-148", "pod_model": "2"},
        "Iridium-164": {"reachid": "REACH-149", "pod_model": "1"},
        "Iridium-147": {"reachid": "REACH-162", "pod_model": "1"},
        "Iridium-149": {"reachid": "REACH-163", "pod_model": "2"},
        "Iridium-152": {"reachid": "REACH-164", "pod_model": "1"},
        "Iridium-145": {"reachid": "REACH-165", "pod_model": "3"},
        "Iridium-180": {"reachid": "REACH-166", "pod_model": "2"},
        "Iridium-153": {"reachid": "REACH-169", "pod_model": "0"},
        "Iridium-156": {"reachid": "REACH-170", "pod_model": "0"},
        "Iridium-158": {"reachid": "REACH-171", "pod_model": "0"},
        "Iridium-159": {"reachid": "REACH-172", "pod_model": "0"},
        "Iridium-165": {"reachid": "REACH-173", "pod_model": "1"},
        "Iridium-168": {"reachid": "REACH-175", "pod_model": "3"},
        "Iridium-150": {"reachid": "REACH-176", "pod_model": "1"},
        "Iridium-171": {"reachid": "REACH-180", "pod_model": "0"},
        "Iridium-160": {"reachid": "REACH-181", "pod_model": "0"},
    }

    return reachids


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
