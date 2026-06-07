"""Tests for Checkpoint course point type mapping."""

import pytest

from gpx_editor.io._course_point_types import (
    GARMIN_POI_TYPES,
    garmin_to_fit_int,
    garmin_to_symbol,
    garmin_type_for_name,
    symbol_to_garmin,
    to_garmin,
)


class TestCheckpointInTypeRegistry:
    """Verify Checkpoint is registered as a valid Garmin type."""

    def test_checkpoint_in_poi_types(self):
        assert "Checkpoint" in GARMIN_POI_TYPES

    def test_to_garmin_normalizes_checkpoint(self):
        assert to_garmin("checkpoint") == "Checkpoint"
        assert to_garmin("Checkpoint") == "Checkpoint"

    def test_fit_enum_value(self):
        assert garmin_to_fit_int("Checkpoint") == 26


class TestSymbolToGarmin:
    """Test symbol_to_garmin for checkpoint-related symbols."""

    def test_exact_checkpoint_symbol(self):
        assert symbol_to_garmin("checkpoint") == "Checkpoint"

    @pytest.mark.parametrize("symbol", [
        "cp",
        "tcp",
        "CP",
        "TCP",
    ])
    def test_cp_tcp_without_number_returns_generic(self, symbol):
        # "cp" and "tcp" alone don't match "checkpoint" keyword exactly
        assert symbol_to_garmin(symbol) == "Generic"


class TestGarminTypeForName:
    """Test garmin_type_for_name for checkpoint patterns."""

    @pytest.mark.parametrize("name,expected", [
        ("Checkpoint", "Checkpoint"),
        ("checkpoint", "Checkpoint"),
        ("Checkpoint Station", "Checkpoint"),
    ])
    def test_checkpoint_keyword(self, name, expected):
        assert garmin_type_for_name(name) == expected

    @pytest.mark.parametrize("name", [
        "CP1",
        "CP 1",
        "CP 10",
        "CP 99",
        "cp1",
        "cp 5",
        "cp"
    ])
    def test_cp_with_number(self, name):
        assert garmin_type_for_name(name) == "Checkpoint"

    @pytest.mark.parametrize("name", [
        "TCP1",
        "TCP 1",
        "TCP 10",
        "tcp5",
        "tcp 5",
        "tcp",
    ])
    def test_tcp_with_number(self, name):
        assert garmin_type_for_name(name) == "Checkpoint"

    @pytest.mark.parametrize("name,expected", [
        ("", "Generic"),
        ("Unknown", "Generic"),
        ("CP A", "Generic"),  # non-numeric suffix
    ])
    def test_fallback_to_generic(self, name, expected):
        assert garmin_type_for_name(name) == expected


class TestGarminToSymbol:
    """Test garmin_to_symbol for checkpoint patterns."""

    def test_checkpoint_to_symbol(self):
        assert garmin_to_symbol("Checkpoint") == "checkpoint"
        assert garmin_to_symbol("checkpoint") == "checkpoint"

    @pytest.mark.parametrize("pattern", [
        "CP 1",
        "CP 10",
        "cp 5",
        "TCP 1",
        "tcp 5",
    ])
    def test_cp_tcp_pattern_to_symbol(self, pattern):
        assert garmin_to_symbol(pattern) == "checkpoint"

    @pytest.mark.parametrize("pattern", [
        "CP",
        "TCP",
        "CP A",
        "CP 1A",
    ])
    def test_invalid_patterns_return_empty(self, pattern):
        assert garmin_to_symbol(pattern) == ""


class TestCheckpointRoundtrip:
    """Test round-trip conversion for checkpoint."""

    def test_symbol_roundtrip(self):
        # Garmin type -> symbol -> Garmin type
        symbol = garmin_to_symbol("Checkpoint")
        assert symbol == "checkpoint"
        assert symbol_to_garmin(symbol) == "Checkpoint"
