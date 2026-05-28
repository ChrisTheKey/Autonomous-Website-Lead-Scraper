"""Tests for crawler robots.txt handling and path blocking."""

import pytest

from app.services.crawler_service import (
    _is_blocked_path,
    _is_priority_path,
    _robots_allows,
)
from urllib.robotparser import RobotFileParser


class TestRobotsHandling:
    def _make_robots(self, content: str) -> RobotFileParser:
        rp = RobotFileParser()
        rp.parse(content.splitlines())
        return rp

    def test_disallowed_path_returns_false(self):
        rp = self._make_robots("User-agent: *\nDisallow: /admin/\n")
        assert not _robots_allows(rp, "https://example.com/admin/dashboard", "*")

    def test_allowed_path_returns_true(self):
        rp = self._make_robots("User-agent: *\nAllow: /\n")
        assert _robots_allows(rp, "https://example.com/kontakt", "*")

    def test_empty_robots_allows_all(self):
        rp = self._make_robots("")
        assert _robots_allows(rp, "https://example.com/kontakt", "*")


class TestPathPriority:
    def test_kontakt_is_priority(self):
        assert _is_priority_path("https://example.com/kontakt")

    def test_impressum_is_priority(self):
        assert _is_priority_path("https://example.com/impressum")

    def test_about_is_priority(self):
        assert _is_priority_path("https://example.com/about-us")

    def test_random_page_not_priority(self):
        assert not _is_priority_path("https://example.com/products/123")


class TestBlockedPaths:
    def test_login_is_blocked(self):
        assert _is_blocked_path("https://example.com/login")

    def test_admin_is_blocked(self):
        assert _is_blocked_path("https://example.com/admin/panel")

    def test_cart_is_blocked(self):
        assert _is_blocked_path("https://example.com/cart")

    def test_checkout_is_blocked(self):
        assert _is_blocked_path("https://example.com/checkout/step1")

    def test_normal_page_not_blocked(self):
        assert not _is_blocked_path("https://example.com/kontakt")

    def test_homepage_not_blocked(self):
        assert not _is_blocked_path("https://example.com/")
