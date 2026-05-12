import os

import pytest

# Force MPL to use non-gui backends for testing.
try:
    import matplotlib
    import matplotlib.pyplot as plt

    HAVE_MATPLOTLIB = True
    matplotlib.use("Agg")
except ImportError:
    HAVE_MATPLOTLIB = False


@pytest.fixture(autouse=True, scope="function")
def default_test_mission(monkeypatch):
    """Ensure tests run with the swxsoc_pipeline mission configuration.

    Tests can still override ``SWXSOC_MISSION`` explicitly if needed.
    """
    import swxsoc
    from swxsoc_reach import config

    monkeypatch.setenv("SWXSOC_MISSION", "swxsoc_pipeline")
    swxsoc._reconfigure()

    mission_name = config.get("mission_name")
    if mission_name is None:
        mission_name = config.get("mission", {}).get("mission_name")
    assert mission_name == "swxsoc_pipeline"
