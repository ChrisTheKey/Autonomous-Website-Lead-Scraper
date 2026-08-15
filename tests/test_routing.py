"""Routing contract tests.

Routes are inspected through the generated OpenAPI schema, so these run without
a database, a broker or a single HTTP request.
"""

import pytest

from app.main import app

REVIEW_PATHS = [
    "/companies/{company_id}/verify",
    "/companies/{company_id}/reject",
    "/companies/{company_id}/mark-contacted",
    "/companies/{company_id}/add-to-suppression",
    "/companies/{company_id}/refresh",
    "/companies/{company_id}/crawl",
    "/companies/{company_id}/analyze-website",
]

# Actions the dashboard builds as `/companies/${id}/${action}`.
DASHBOARD_ACTIONS = [
    "verify",
    "reject",
    "mark-contacted",
    "add-to-suppression",
    "refresh",
]

OTHER_PATHS = [
    "/health",
    "/search",
    "/searches",
    "/searches/{search_id}",
    "/companies",
    "/companies/{company_id}",
    "/companies/{company_id}/notes",
    "/candidates",
    "/export",
    "/export/no-website-candidates",
]


def _paths() -> dict:
    return app.openapi()["paths"]


class TestReviewRoutes:
    @pytest.mark.parametrize("path", REVIEW_PATHS)
    def test_review_path_registered(self, path):
        assert path in _paths()

    @pytest.mark.parametrize("path", REVIEW_PATHS)
    def test_review_path_accepts_post(self, path):
        assert "post" in _paths()[path]

    def test_no_duplicated_companies_prefix(self):
        assert [p for p in _paths() if "/companies/companies" in p] == []

    def test_no_path_segment_is_repeated_back_to_back(self):
        for path in _paths():
            segments = [s for s in path.split("/") if s]
            doubled = [
                a for a, b in zip(segments, segments[1:]) if a == b and not a.startswith("{")
            ]
            assert not doubled, f"{path} repeats {doubled}"


class TestDashboardContract:
    @pytest.mark.parametrize("action", DASHBOARD_ACTIONS)
    def test_dashboard_action_has_matching_route(self, action):
        assert f"/companies/{{company_id}}/{action}" in _paths()


class TestOtherRoutesUnchanged:
    @pytest.mark.parametrize("path", OTHER_PATHS)
    def test_route_still_registered(self, path):
        assert path in _paths()

    def test_total_route_count_is_stable(self):
        # 7 review actions + 10 other documented paths.
        assert len(_paths()) == len(REVIEW_PATHS) + len(OTHER_PATHS)
