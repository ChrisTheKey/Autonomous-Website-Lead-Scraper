"""Tests for crawler robots.txt handling and path blocking."""

import pytest

from app.services.crawler_service import (
    _is_blocked_path,
    _is_priority_path,
    _robots_allows,
    canonical_resource_url,
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


class TestFragmentCanonicalisation:
    def test_plain_url_is_unchanged(self):
        assert canonical_resource_url("https://example.ch/") == "https://example.ch/"

    def test_hash_fragment_is_dropped(self):
        assert canonical_resource_url("https://example.ch/#kontakt") == "https://example.ch/"

    def test_hashbang_fragment_is_dropped(self):
        assert canonical_resource_url("https://example.ch/#!/kontakt") == "https://example.ch/"

    def test_different_fragments_collapse_to_one_resource(self):
        variants = [
            "https://example.ch/",
            "https://example.ch/#kontakt",
            "https://example.ch/#content",
            "https://example.ch/#!/referenzen",
            "https://example.ch/#!/uberuns",
        ]
        assert len({canonical_resource_url(u) for u in variants}) == 1

    def test_fragment_on_subpage_is_dropped(self):
        assert (
            canonical_resource_url("https://example.ch/kontakt#team")
            == "https://example.ch/kontakt"
        )

    def test_distinct_paths_stay_distinct(self):
        pages = {
            canonical_resource_url("https://example.ch/kontakt"),
            canonical_resource_url("https://example.ch/impressum"),
        }
        assert len(pages) == 2

    def test_query_string_is_preserved(self):
        assert (
            canonical_resource_url("https://example.ch/suche?q=maler")
            == "https://example.ch/suche?q=maler"
        )

    def test_distinct_query_strings_are_not_merged(self):
        pages = {
            canonical_resource_url("https://example.ch/p?id=1"),
            canonical_resource_url("https://example.ch/p?id=2"),
        }
        assert len(pages) == 2

    def test_query_kept_while_fragment_dropped(self):
        assert (
            canonical_resource_url("https://example.ch/p?id=1#top")
            == "https://example.ch/p?id=1"
        )

    def test_host_and_scheme_are_untouched(self):
        assert (
            canonical_resource_url("http://sub.example.ch/a#x") == "http://sub.example.ch/a"
        )

    def test_page_budget_not_consumed_by_fragment_duplicates(self):
        # The ten URLs the crawler actually stored for company 1: two real
        # resources, eight fragment variants of them.
        observed = [
            "https://witschimalerei.ch/",
            "https://witschimalerei.ch/impressum",
            "https://witschimalerei.ch/impressum#!/kontakt",
            "https://witschimalerei.ch/impressum#!/referenzen",
            "https://witschimalerei.ch/impressum#!/uberuns",
            "https://witschimalerei.ch/impressum#content",
            "https://witschimalerei.ch/#content",
            "https://witschimalerei.ch/#!/uberuns",
            "https://witschimalerei.ch/#!/referenzen",
            "https://witschimalerei.ch/impressum#elementor-action%3Aaction%3Dpopup",
        ]
        assert len({canonical_resource_url(u) for u in observed}) == 2

    def test_stored_url_carries_no_fragment(self):
        for url in ("https://example.ch/#a", "https://example.ch/p?q=1#b"):
            assert "#" not in canonical_resource_url(url)


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
