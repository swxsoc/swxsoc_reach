"""Tests for the Flavor Flag enum."""

import json
from pathlib import Path

import pytest

from swxsoc_reach.util.enums import (
    Flavor,
    SensorId,
    load_reach_id_dosimeter_relationship,
    sensor_ids_for_flavor,
)


class TestFlavorMembers:
    def test_single_members_exist(self):
        for name in ("U", "V", "W", "X", "Y", "Z"):
            assert hasattr(Flavor, name)

    def test_all_member_exists(self):
        assert hasattr(Flavor, "ALL")

    def test_all_contains_every_single_flavor(self):
        for member in (Flavor.U, Flavor.V, Flavor.W, Flavor.X, Flavor.Y, Flavor.Z):
            assert member in Flavor.ALL

    def test_bitwise_combination(self):
        combo = Flavor.U | Flavor.W
        assert Flavor.U in combo
        assert Flavor.W in combo
        assert Flavor.V not in combo

    def test_values_are_distinct_powers_of_two(self):
        singles = [Flavor.U, Flavor.V, Flavor.W, Flavor.X, Flavor.Y, Flavor.Z]
        values = [f.value for f in singles]
        # All values should be unique powers of two
        assert len(set(values)) == len(values)
        for v in values:
            assert v > 0 and (v & (v - 1)) == 0


class TestFlavorFromStr:
    def test_lowercase_lookup(self):
        assert Flavor.from_str("w") is Flavor.W

    def test_uppercase_lookup(self):
        assert Flavor.from_str("U") is Flavor.U

    def test_mixed_case_lookup(self):
        assert Flavor.from_str("z") is Flavor.Z

    def test_all_single_flavors(self):
        for name in ("U", "V", "W", "X", "Y", "Z"):
            assert Flavor.from_str(name) is Flavor[name]

    def test_flavor_phrase_string(self):
        assert Flavor.from_str("DOSE1 (Flavor X) in rad/second") is Flavor.X

    def test_flavor_phrase_string_lowercase_letter(self):
        assert Flavor.from_str("DOSE1 (Flavor w) in rad/second") is Flavor.W

    def test_flavor_phrase_string_no_parentheses(self):
        assert Flavor.from_str("Flavor Z") is Flavor.Z

    def test_unknown_flavor_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown flavor"):
            Flavor.from_str("Q")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            Flavor.from_str("")


class TestFlavorLabel:
    def test_each_single_flavor_has_label(self):
        for member in (Flavor.U, Flavor.V, Flavor.W, Flavor.X, Flavor.Y, Flavor.Z):
            label = member.label
            assert isinstance(label, str)
            assert len(label) > 0

    def test_all_has_label(self):
        label = Flavor.ALL.label
        assert isinstance(label, str)

    def test_w_label_content(self):
        assert "12 MeV" in Flavor.W.label

    def test_z_label_content(self):
        assert "50 keV" in Flavor.Z.label

    def test_unknown_composite_raises_key_error(self):
        combo = Flavor.U | Flavor.V  # Not in labels dict
        with pytest.raises(KeyError):
            _ = combo.label


class TestSensorId:
    def test_sensor_members_exist(self):
        assert hasattr(SensorId, "REACH_101")
        assert hasattr(SensorId, "REACH_181")
        assert hasattr(SensorId, "ALL")

    def test_from_str_hyphen(self):
        assert SensorId.from_str("REACH-101") is SensorId.REACH_101

    def test_from_str_underscore(self):
        assert SensorId.from_str("reach_181") is SensorId.REACH_181

    def test_from_str_numeric(self):
        assert SensorId.from_str("176") is SensorId.REACH_176

    def test_membership_in_all(self):
        assert SensorId.REACH_133 in SensorId.ALL

    def test_unknown_sensor_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown sensor id"):
            SensorId.from_str("REACH-999")


class TestReachIdDosimeterRelationshipCoverage:
    @staticmethod
    def _load_relationship_json() -> dict:
        path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "reach_id_dosimeter_relationship.json"
        )
        with path.open(encoding="utf-8-sig") as f:
            return json.load(f)

    def test_sensor_ids_match_sensorid_enum(self):
        relationship = self._load_relationship_json()

        file_sensor_ids = set(relationship.keys())
        enum_sensor_ids = {
            str(sensor) for sensor in SensorId if sensor is not SensorId.ALL
        }

        assert file_sensor_ids == enum_sensor_ids

    def test_flavors_match_flavor_enum(self):
        relationship = self._load_relationship_json()

        file_flavor_names = {
            Flavor.from_str(flavor).name
            for payload in relationship.values()
            for flavor in payload["dosimeters"]
        }
        enum_flavor_names = {
            flavor.name for flavor in Flavor if flavor is not Flavor.ALL
        }

        assert file_flavor_names == enum_flavor_names


class TestReachIdDosimeterRelationshipLoader:
    def test_loader_converts_strings_to_enums(self):
        relationship = load_reach_id_dosimeter_relationship()

        assert relationship
        assert all(isinstance(sensor_id, SensorId) for sensor_id in relationship)
        assert all(
            isinstance(flavor, Flavor)
            for dosimeters in relationship.values()
            for flavor in dosimeters
        )

    def test_loader_sensor_coverage_matches_enum(self):
        relationship = load_reach_id_dosimeter_relationship()

        loaded_sensor_ids = set(relationship.keys())
        enum_sensor_ids = {sensor for sensor in SensorId if sensor is not SensorId.ALL}

        assert loaded_sensor_ids == enum_sensor_ids


class TestSensorIdsForFlavor:
    def test_returns_sensor_ids_for_flavor_enum(self):
        sensors = sensor_ids_for_flavor(Flavor.Z)

        expected = {
            SensorId.REACH_169,
            SensorId.REACH_170,
            SensorId.REACH_171,
            SensorId.REACH_172,
            SensorId.REACH_180,
            SensorId.REACH_181,
        }
        assert set(sensors) == expected

    def test_accepts_string_flavor(self):
        from_enum = sensor_ids_for_flavor(Flavor.V)
        from_string = sensor_ids_for_flavor("Flavor V")

        assert set(from_string) == set(from_enum)
