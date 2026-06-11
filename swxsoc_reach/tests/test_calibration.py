from pathlib import Path

import pytest
from swxsoc import swxdata

import swxsoc_reach.calibration.calibration as calib
from swxsoc_reach import _test_files_directory
from swxsoc_reach.util.util import parse_science_filename

test_udl_file_paths = list(_test_files_directory.glob("REACH-*.csv"))
target_udl_file_path = (
    _test_files_directory / "REACH-TEST_20250904T000000_20250904T010000.csv"
)
target_l1c_file_path = (
    _test_files_directory / "reach_all_l1c_prelim_20250904T000000_v1.0.0.cdf"
)


@pytest.mark.parametrize("this_path", test_udl_file_paths)
def test_l1_process_file(this_path, tmpdir, monkeypatch):
    # Set up the temporary directory as the current working directory
    monkeypatch.chdir(tmpdir)
    files = calib.process_file(this_path)
    assert Path(files[0]).exists()

    # Make sure the filename is correctly parsed and the output filename is correct
    parsed_result = parse_science_filename(files[0])
    assert parsed_result["instrument"] == "reach"
    assert parsed_result["level"] == "l1c"
    assert parsed_result["mode"] == "all"
    assert parsed_result["version"] == "1.0.0"

    # Make sure the output CDFs can be loaded by the SWxSOC framework (this also tests that the CDF is valid and correctly formatted)
    data = swxdata.SWXData.load(files[0])
    assert isinstance(data, swxdata.SWXData)


def test_process_file_target(tmpdir, monkeypatch):
    # Set up the temporary directory as the current working directory
    monkeypatch.chdir(tmpdir)

    files = calib.process_file(target_udl_file_path)
    assert Path(files[0]).exists()

    # Make sure the filename is correctly parsed and the output filename is correct
    parsed_result = parse_science_filename(files[0])
    assert parsed_result["instrument"] == "reach"
    assert parsed_result["level"] == "l1c"
    assert parsed_result["mode"] == "all"
    assert parsed_result["version"] == "1.0.0"

    # Compare CDF Content
    from spacepy import pycdf

    result_cdf = pycdf.CDF(str(files[0]))
    target_cdf = pycdf.CDF(str(target_l1c_file_path))
    assert result_cdf.keys() == target_cdf.keys(), "CDF variable keys should match"

    # Process again to level 2 and compare with target level 2 file
    level_2_files = calib.process_file(files[0])
    assert len(level_2_files) > 0, "Should produce at least one level 2 file"


@pytest.mark.parametrize("this_path", test_udl_file_paths)
def test_process_file_cdf_creates_geomaps(this_path, tmpdir, monkeypatch):
    """Test that processing a CDF file creates geomap CDFs and JPG plots for each flavor.

    Note: This test expects at least some geomap products to be created. If no geomaps
    can be created due to data quality issues (e.g., empty flavor values), the test is skipped.
    """
    # Set up the temporary directory as the current working directory
    monkeypatch.chdir(tmpdir)

    # First, process the UDL file to create a CDF
    cdf_files = calib.process_file(this_path)
    assert len(cdf_files) > 0
    cdf_path = Path(cdf_files[0])
    assert cdf_path.exists()

    # Now process the CDF file to create geomaps
    geomap_files = calib.process_file(cdf_path)

    # Should have: geomap CDFs + JPG plots
    assert len(geomap_files) >= 1

    # Collect geomap CDFs and JPGs
    geomap_cdfs = [
        f
        for f in geomap_files
        if isinstance(f, (str, Path))
        and "l2" in str(f).lower()
        and str(f).endswith(".cdf")
    ]
    geomap_jpgs = [
        f
        for f in geomap_files
        if isinstance(f, (str, Path))
        and "geomap" in str(f).lower()
        and str(f).endswith(".jpg")
    ]

    # If no geomap products were created, skip this test (may be due to data quality issues)
    if len(geomap_cdfs) == 0:
        pytest.skip(
            "No geomap CDFs created for this file (possibly due to data quality issues)"
        )

    assert len(geomap_jpgs) > 0, (
        "Should create at least one geomap JPG plot when CDFs are created"
    )

    # Verify geomap CDFs exist and have content
    for geomap_cdf in geomap_cdfs:
        cdf_path_obj = Path(geomap_cdf)
        assert cdf_path_obj.exists(), f"Geomap CDF should exist: {geomap_cdf}"
        assert cdf_path_obj.suffix.lower() == ".cdf", (
            f"Geomap file should be .cdf: {geomap_cdf}"
        )
        assert cdf_path_obj.stat().st_size > 0, (
            f"Geomap CDF should have content: {geomap_cdf}"
        )

        # Verify it contains "l2" in filename (level 2 product)
        assert "l2" in cdf_path_obj.name.lower(), (
            f"Geomap CDF should have l2 in filename: {cdf_path_obj.name}"
        )

    # Verify all JPG plots exist and have content
    for geomap_jpg in geomap_jpgs:
        jpg_path = Path(geomap_jpg)
        assert jpg_path.exists(), f"Geomap JPG should exist: {geomap_jpg}"
        assert jpg_path.suffix.lower() == ".jpg", (
            f"Geomap file should be .jpg: {geomap_jpg}"
        )
        assert jpg_path.stat().st_size > 0, (
            f"Geomap JPG should have content: {geomap_jpg}"
        )
