"""Tests for deduplication logic."""

import pytest

from app.services.dedupe_service import normalize_name, normalize_phone


class TestNormalizeName:
    def test_strips_gmbh(self):
        assert normalize_name("Muster GmbH") == "muster"

    def test_strips_ag(self):
        assert normalize_name("Test AG") == "test"

    def test_lowercases(self):
        assert normalize_name("MUSTER") == "muster"

    def test_collapses_whitespace(self):
        assert normalize_name("Muster   GmbH") == "muster"

    def test_handles_umlauts(self):
        result = normalize_name("Müller GmbH")
        assert "gmbh" not in result
        assert result  # non-empty


class TestNormalizePhone:
    def test_strips_spaces_and_dashes(self):
        result = normalize_phone("+41 44 123 45 67")
        assert " " not in result
        assert "-" not in result

    def test_returns_none_for_empty(self):
        assert normalize_phone(None) is None
        assert normalize_phone("") is None

    def test_swiss_prefix_0041(self):
        result = normalize_phone("004144123456")
        assert result.startswith("+41")

    def test_german_prefix_0049(self):
        result = normalize_phone("004930123456")
        assert result.startswith("+49")

    def test_preserves_plus_prefix(self):
        result = normalize_phone("+41441234567")
        assert result.startswith("+41")
