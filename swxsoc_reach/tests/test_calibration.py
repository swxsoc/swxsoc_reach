from pathlib import Path

import pytest
from swxsoc import swxdata

import swxsoc_reach.calibration.calibration as calib
from swxsoc_reach import _test_files_directory
from swxsoc_reach.util.util import parse_science_filename

test_file_paths = _test_files_directory.glob("REACH-*")


@pytest.mark.parametrize("this_path", list(test_file_paths))
def test_process_file(this_path, tmpdir, monkeypatch):
    # Set up the temporary directory as the current working directory
    monkeypatch.chdir(tmpdir)
    files = calib.process_file(this_path)
    assert Path(files[0]).exists()

    # Make sure the filename is correctly parsed and the output filename is correct
    parsed_result = parse_science_filename(files[0])
    assert parsed_result["instrument"] == "reach"
    assert parsed_result["level"] == "l1"
    assert parsed_result["mode"] == "all"
    assert parsed_result["version"] == "1.0.0"

    # Make sure the output CDFs can be loaded by the SWxSOC framework (this also tests that the CDF is valid and correctly formatted)
    data = swxdata.SWXData.load(files[0])
    assert isinstance(data, swxdata.SWXData)
