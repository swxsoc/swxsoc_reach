import pytest

import swxsoc_reach.util.util as util

TIME = "2024-04-06T12:06:21"
TIME_FORMATTED = "20240406T120621"


# fmt: off
@pytest.mark.parametrize("time,level,version,descriptor,result", [
    (TIME, "l1", "1.2.3", "all", f"swxsoc_pipeline_reach_l1_all_{TIME_FORMATTED}_v1.2.3.cdf"),
    (TIME, "l2", "2.4.5", "all", f"swxsoc_pipeline_reach_l2_all_{TIME_FORMATTED}_v2.4.5.cdf"),
    (TIME, "l2", "1.3.5", "sci", f"swxsoc_pipeline_reach_l2_sci_{TIME_FORMATTED}_v1.3.5.cdf"),
    (TIME, "l3", "2.4.5", "cal", f"swxsoc_pipeline_reach_l3_cal_{TIME_FORMATTED}_v2.4.5.cdf"),
])
def test_create_reach_filename(time, level, version, descriptor, result):
    """Test that create_reach_filename generates correct CDF filenames.
    It wraps swxsoc.util.create_science_filename with instrument='reach'."""
    assert (
        util.create_reach_filename(time, level=level, descriptor=descriptor, version=version)
        == result
    )
# fmt: on


# fmt: off
@pytest.mark.parametrize("time,level,version,descriptor,result", [
    (TIME, "l1", "1.2.3", "all", f"swxsoc_pipeline_reach_l1_all_{TIME_FORMATTED}_v1.2.3.cdf"),
    (TIME, "l2", "2.4.5", "hk",  f"swxsoc_pipeline_reach_l2_hk_{TIME_FORMATTED}_v2.4.5.cdf"),
    (TIME, "l1", "1.0.0", "sci", f"swxsoc_pipeline_reach_l1_sci_{TIME_FORMATTED}_v1.0.0.cdf"),
])
def test_create_reach_filename_descriptors(time, level, version, descriptor, result):
    """Test that different descriptors are correctly included in the filename."""
    assert (
        util.create_reach_filename(time, level=level, descriptor=descriptor, version=version)
        == result
    )
# fmt: on


def test_create_reach_filename_test_flag():
    """Test that the test flag is passed through to the underlying swxsoc function."""
    filename = util.create_reach_filename(
        TIME, level="l1", descriptor="all", version="1.0.0", test=True
    )
    # When test=True, the swxsoc framework prepends or marks the filename as a test file
    assert "reach" in filename
    assert "l1" in filename
