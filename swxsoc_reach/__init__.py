# see license/LICENSE.rst
import os
from pathlib import Path

try:
    from ._version import version as __version__
    from ._version import version_tuple
except ImportError:
    __version__ = "unknown version"
    version_tuple = (0, 0, "unknown version")

# Get SWXSOC_MISSIONS environment variable if it exists or use default for mission
SWXSOC_MISSION = os.getenv("SWXSOC_MISSION", "swxsoc_pipeline")
os.environ["SWXSOC_MISSION"] = SWXSOC_MISSION

from swxsoc import config as swxsoc_config  # noqa: E402
from swxsoc import log as swxsoc_log

from swxsoc_reach.util.enums import load_reach_id_dosimeter_relationship

# Load user configuration
config = swxsoc_config
log = swxsoc_log

_package_directory = Path(__file__).parent
_data_directory = _package_directory / "data"
_test_files_directory = _package_directory / "data" / "test"
_test_file_track = _test_files_directory / "reach_all_l1c_prelim_20250904T000000_v1.0.0.cdf"

REACH_ID_DOSIMETER_RELATIONSHIP = load_reach_id_dosimeter_relationship()

# Then you can be explicit to control what ends up in the namespace,
__all__ = ["config", "REACH_ID_DOSIMETER_RELATIONSHIP"]

log.debug(f"swxsoc_reach version: {__version__}")
