"""Tests for the Flavor Flag enum."""

import pytest

from swxsoc_reach.util.enums import Flavor, SensorId


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
