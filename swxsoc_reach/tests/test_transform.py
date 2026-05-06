
import pandas as pd
import pytest

from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.io.file_tools import read_udl_csv
from swxsoc_reach import _test_files_directory


def _make_input_dataframe(descriptors: list[str]) -> pd.DataFrame:
    rows = []
    for i, descriptor in enumerate(descriptors):
        rows.append(
            {
                "createdAt": f"2026-01-01T00:00:0{i}Z",
                "idSensor": "REACH-001",
                "obDescription": "DOSE2 (Flavor Z) in rad/second",
                "obTime": f"2026-01-01T00:00:0{i}Z",
                "obValue": 1.0 + i,
                "observatoryName": "REACH",
                "lat": 10.0,
                "lon": 20.0,
                "alt": 500.0,
                "obQuality": 1,
                "senPos0": 1000.0,
                "senPos1": 2000.0,
                "senPos2": 3000.0,
                "descriptor": descriptor,
            }
        )
    return pd.DataFrame(rows)


def test_build_swxdata_sets_udl_source_from_descriptor():
    data = _make_input_dataframe(["QUICKLOOK", "QUICKLOOK"])

    reach_data = build_swxdata(data, version="1.2.3")

    assert reach_data.meta["UDL_Source"] == "QUICKLOOK"
    assert reach_data.meta["Data_version"] == "1.2.3"


def test_build_swxdata_raises_without_descriptor_column():
    data = _make_input_dataframe(["QUICKLOOK"]).drop(columns=["descriptor"])

    with pytest.raises(ValueError, match="must contain a 'descriptor' column"):
        build_swxdata(data)


def test_build_swxdata_raises_with_multiple_descriptors():
    data = _make_input_dataframe(["QUICKLOOK", "PROVISIONAL"])

    with pytest.raises(ValueError, match="Expected only one unique descriptor value"):
        build_swxdata(data)


@pytest.mark.parametrize(
    "input_filename,expected_source",
    [
        ("REACH-ALL_20250901T000000_20250902T000000.csv", "PROVISIONAL"),
        ("REACH-ALL_20251205T060517_20251205T060517.csv", "QUICKLOOK"),
    ],
)
def test_build_swxdata_sets_udl_source_from_csv_fixture(
    input_filename: str, expected_source: str
):
    data = read_udl_csv(_test_files_directory / input_filename)

    reach_data = build_swxdata(data)

    assert reach_data.meta["UDL_Source"] == expected_source
