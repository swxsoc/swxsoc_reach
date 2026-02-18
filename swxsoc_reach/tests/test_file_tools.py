import pandas as pd
import pytest

import swxsoc_reach.io.file_tools as file_tools
from swxsoc_reach import _test_files_directory

test_file_paths = _test_files_directory.glob("REACH-*")


@pytest.mark.parametrize("this_path", list(test_file_paths))
def test_file_read(this_path):
    """Test that all test files can be read"""
    ts = file_tools.read_file(this_path)
    assert isinstance(ts, pd.DataFrame)
