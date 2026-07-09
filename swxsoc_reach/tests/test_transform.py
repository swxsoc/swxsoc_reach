import pandas as pd
import pytest

from swxsoc_reach import _test_files_directory
from swxsoc_reach.calibration import transform
from swxsoc_reach.io.file_tools import read_udl_csv
from swxsoc_reach.util.enums import SensorId


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


def test_impute_sensor_metadata_fills_missing_ids_from_lookup(monkeypatch):
    monkeypatch.setattr(
        transform,
        "get_reachid_lut",
        lambda: {"Iridium-102": {"reachid": "REACH-101", "pod_model": "1"}},
    )

    data = pd.DataFrame(
        [
            {"idSensor": pd.NA, "observatoryName": "Iridium-102"},
            {"idSensor": "REACH-999", "observatoryName": "Iridium-102"},
            {"idSensor": pd.NA, "observatoryName": "Unknown-Sat"},
        ]
    )

    result = transform.impute_sensor_metadata(data.copy())

    assert len(result) == 2
    assert result.loc[0, "idSensor"] == "REACH-101"
    assert result.loc[1, "idSensor"] == "REACH-999"
    assert "Unknown-Sat" not in result["observatoryName"].values


def test_build_swxdata_sets_udl_source_from_descriptor():
    data = _make_input_dataframe(["QUICKLOOK", "QUICKLOOK"])

    reach_data = transform.build_swxdata(data, version="1.2.3")

    assert reach_data.meta["UDL_Source"] == "QUICKLOOK"
    assert reach_data.meta["Data_version"] == "1.2.3"


def test_build_swxdata_raises_without_descriptor_column():
    data = _make_input_dataframe(["QUICKLOOK"]).drop(columns=["descriptor"])

    with pytest.raises(ValueError, match="must contain a 'descriptor' column"):
        transform.build_swxdata(data)


def test_build_swxdata_raises_with_multiple_descriptors():
    data = _make_input_dataframe(["QUICKLOOK", "PROVISIONAL"])

    with pytest.raises(ValueError, match="Expected only one unique descriptor value"):
        transform.build_swxdata(data)


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

    reach_data = transform.build_swxdata(data)

    assert reach_data.meta["UDL_Source"] == expected_source


def _make_sparse_sensor_day(sensor_rows: list[dict[str, str | float]]) -> pd.DataFrame:
    rows = []
    for i, payload in enumerate(sensor_rows):
        rows.append(
            {
                "createdAt": f"2026-01-01T00:00:0{i}Z",
                "idSensor": payload["idSensor"],
                "obDescription": payload["obDescription"],
                "obTime": payload["obTime"],
                "obValue": payload["obValue"],
                "observatoryName": "REACH",
                "lat": payload.get("lat", 10.0),
                "lon": payload.get("lon", 20.0),
                "alt": payload.get("alt", 500.0),
                "obQuality": payload.get("obQuality", 1),
                "senPos0": payload.get("senPos0", 1000.0),
                "senPos1": payload.get("senPos1", 2000.0),
                "senPos2": payload.get("senPos2", 3000.0),
                "descriptor": "PROVISIONAL",
            }
        )
    return pd.DataFrame(rows)


def test_build_swxdata_emits_canonical_sensor_and_flavor_axes():
    data = _make_sparse_sensor_day(
        [
            {
                "idSensor": "REACH-101",
                "obDescription": "DOSE1 (Flavor X) in rad/second",
                "obTime": "2026-01-01T00:00:00Z",
                "obValue": 10.0,
            },
            {
                "idSensor": "REACH-101",
                "obDescription": "DOSE2 (Flavor W) in rad/second",
                "obTime": "2026-01-01T00:00:00Z",
                "obValue": 20.0,
            },
            {
                "idSensor": "REACH-170",
                "obDescription": "flavor X",
                "obTime": "2026-01-01T00:00:01Z",
                "obValue": 30.0,
            },
        ]
    )

    reach_data = transform.build_swxdata(data)

    assert reach_data["dose_rate"].data.shape == (2, 32, 2)
    assert reach_data["lat"].data.shape == (2, 32)
    assert reach_data["dosimeter_flavors"].data.shape == (32, 2)

    sensor_idx_101 = SensorId.REACH_101.to_index()
    sensor_idx_170 = SensorId.REACH_170.to_index()
    missing_sensor_idx = SensorId.REACH_102.to_index()

    assert reach_data["dose_rate"].data[0, sensor_idx_101, 0] == 10.0
    assert reach_data["dose_rate"].data[0, sensor_idx_101, 1] == 20.0
    assert reach_data["dose_rate"].data[1, sensor_idx_170, 0] == 30.0
    assert pd.isna(reach_data["dose_rate"].data[:, missing_sensor_idx, :]).all()
    assert pd.isna(reach_data["lat"].data[:, missing_sensor_idx]).all()


def test_build_swxdata_keeps_non_time_dims_stable_across_days():
    day_1 = _make_sparse_sensor_day(
        [
            {
                "idSensor": "REACH-101",
                "obDescription": "DOSE1 (Flavor X) in rad/second",
                "obTime": "2026-01-01T00:00:00Z",
                "obValue": 1.0,
            },
            {
                "idSensor": "REACH-101",
                "obDescription": "DOSE1 (Flavor X) in rad/second",
                "obTime": "2026-01-01T00:00:01Z",
                "obValue": 1.1,
            },
        ]
    )
    day_2 = _make_sparse_sensor_day(
        [
            {
                "idSensor": "REACH-181",
                "obDescription": "DOSE2 (Flavor Z) in rad/second",
                "obTime": "2026-01-02T00:00:00Z",
                "obValue": 2.0,
            },
            {
                "idSensor": "REACH-181",
                "obDescription": "DOSE2 (Flavor Z) in rad/second",
                "obTime": "2026-01-02T00:00:01Z",
                "obValue": 2.1,
            },
        ]
    )

    reach_day_1 = transform.build_swxdata(day_1)
    reach_day_2 = transform.build_swxdata(day_2)

    assert reach_day_1["dose_rate"].data.shape[1:] == (32, 2)
    assert reach_day_2["dose_rate"].data.shape[1:] == (32, 2)
    assert reach_day_1["lat"].data.shape[1] == 32
    assert reach_day_2["lat"].data.shape[1] == 32
