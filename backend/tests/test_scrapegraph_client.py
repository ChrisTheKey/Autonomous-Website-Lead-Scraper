"""
Tests for the ScrapeGraphAI wrapper.

The module under test is loaded from its file path with stubs for
``app.core.config`` and ``scrapegraphai`` in ``sys.modules``, so the suite runs
without the (heavy, optional) dependency and without a populated .env.
"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "ai" / "scrapegraph_client.py"


class FakeGraph:
    """Records how the wrapper instantiated it and returns a canned answer."""

    calls: list[dict] = []
    answer: object = {}

    def __init__(self, **kwargs):
        type(self).calls.append(kwargs)
        self.kwargs = kwargs

    def run(self):
        return type(self).answer

    def get_considered_urls(self):
        return ["https://example.com/impressum"]


def _load(monkeypatch, *, respect_robots=False, graphs_module=None):
    settings = types.SimpleNamespace(
        openai_api_key="test-key",
        scrapegraph_model="gpt-4o-mini",
        scrapegraph_headless=True,
        scrapegraph_verbose=False,
        scrapegraph_timeout=120,
        scrapegraph_max_results=3,
        scrapegraph_respect_robots=respect_robots,
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = []
    core_pkg = types.ModuleType("app.core")
    core_pkg.__path__ = []
    config_mod = types.ModuleType("app.core.config")
    config_mod.settings = settings

    for name, module in {
        "app": app_pkg,
        "app.core": core_pkg,
        "app.core.config": config_mod,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    if graphs_module is not None:
        sg_pkg = types.ModuleType("scrapegraphai")
        sg_pkg.__path__ = []
        sg_pkg.graphs = graphs_module
        monkeypatch.setitem(sys.modules, "scrapegraphai", sg_pkg)
        monkeypatch.setitem(sys.modules, "scrapegraphai.graphs", graphs_module)

    spec = importlib.util.spec_from_file_location("scrapegraph_client_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec so pydantic can resolve the module's own annotations.
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module, settings


def _graphs_stub(**graph_classes):
    module = types.ModuleType("scrapegraphai.graphs")
    for name, cls in graph_classes.items():
        setattr(module, name, cls)
    return module


@pytest.fixture(autouse=True)
def _reset_fake_graph():
    FakeGraph.calls = []
    FakeGraph.answer = {}
    yield


class TestGraphConfig:
    def test_model_gets_provider_prefix(self, monkeypatch):
        module, _ = _load(monkeypatch)
        assert module.build_graph_config()["llm"]["model"] == "openai/gpt-4o-mini"

    def test_explicit_provider_is_kept(self, monkeypatch):
        module, settings = _load(monkeypatch)
        settings.scrapegraph_model = "anthropic/claude-sonnet-4-5"
        assert module.build_graph_config()["llm"]["model"] == "anthropic/claude-sonnet-4-5"

    def test_config_comes_from_settings(self, monkeypatch):
        module, _ = _load(monkeypatch)
        config = module.build_graph_config()
        assert config["llm"]["api_key"] == "test-key"
        assert config["headless"] is True
        assert config["verbose"] is False
        assert config["timeout"] == 120

    def test_llm_override_merges_instead_of_replacing(self, monkeypatch):
        module, _ = _load(monkeypatch)
        config = module.build_graph_config(llm={"temperature": 0.5}, headless=False)
        assert config["llm"]["api_key"] == "test-key"
        assert config["llm"]["temperature"] == 0.5
        assert config["headless"] is False


class TestScrapeLead:
    def test_passes_prompt_source_and_schema_to_graph(self, monkeypatch):
        graphs = _graphs_stub(SmartScraperGraph=FakeGraph)
        module, _ = _load(monkeypatch, graphs_module=graphs)
        FakeGraph.answer = {"company_name": "Muster GmbH", "phone": "+41441234567"}

        lead = asyncio.run(module.scrape_lead("https://example.com", "Extract the contact data"))

        assert lead.company_name == "Muster GmbH"
        assert lead.phone == "+41441234567"
        assert lead.email is None
        call = FakeGraph.calls[0]
        assert call["prompt"] == "Extract the contact data"
        assert call["source"] == "https://example.com"
        assert call["schema"] is module.ScrapedLead

    def test_html_source_is_passed_through_unchanged(self, monkeypatch):
        graphs = _graphs_stub(SmartScraperGraph=FakeGraph)
        module, _ = _load(monkeypatch, graphs_module=graphs)
        FakeGraph.answer = {"company_name": "Muster GmbH"}
        html = "<html><body>Muster GmbH</body></html>"

        lead = asyncio.run(module.scrape_lead_from_html(html, "https://example.com"))

        assert lead.company_name == "Muster GmbH"
        assert FakeGraph.calls[0]["source"] == html

    def test_prose_answer_is_rejected(self, monkeypatch):
        graphs = _graphs_stub(SmartScraperGraph=FakeGraph)
        module, _ = _load(monkeypatch, graphs_module=graphs)
        FakeGraph.answer = "No answer found."

        with pytest.raises(ValueError):
            asyncio.run(module.scrape_lead("https://example.com"))

    def test_missing_dependency_raises_actionable_error(self, monkeypatch):
        module, _ = _load(monkeypatch)
        monkeypatch.setitem(sys.modules, "scrapegraphai", None)

        with pytest.raises(module.ScrapeGraphUnavailableError, match="pip install"):
            asyncio.run(module.scrape_lead("https://example.com"))


class TestRobots:
    def test_disallowed_url_is_never_fetched(self, monkeypatch):
        graphs = _graphs_stub(SmartScraperGraph=FakeGraph)
        module, _ = _load(monkeypatch, respect_robots=True, graphs_module=graphs)

        async def _deny(url):
            return False

        monkeypatch.setattr(module, "robots_allow", _deny)

        with pytest.raises(module.RobotsDisallowedError):
            asyncio.run(module.scrape_lead("https://example.com"))
        assert FakeGraph.calls == []

    def test_disallowed_urls_are_filtered_from_a_batch(self, monkeypatch):
        graphs = _graphs_stub(SmartScraperMultiGraph=FakeGraph)
        module, _ = _load(monkeypatch, respect_robots=True, graphs_module=graphs)
        FakeGraph.answer = {"leads": [{"company_name": "Muster GmbH"}]}

        async def _deny_second(url):
            return url != "https://blocked.example.com"

        monkeypatch.setattr(module, "robots_allow", _deny_second)

        batch = asyncio.run(
            module.scrape_leads(["https://example.com", "https://blocked.example.com"])
        )

        assert [lead.company_name for lead in batch.leads] == ["Muster GmbH"]
        assert FakeGraph.calls[0]["source"] == ["https://example.com"]

    def test_check_is_skipped_when_disabled(self, monkeypatch):
        graphs = _graphs_stub(SmartScraperGraph=FakeGraph)
        module, _ = _load(monkeypatch, respect_robots=False, graphs_module=graphs)
        FakeGraph.answer = {"company_name": "Muster GmbH"}

        def _explode(url):
            raise AssertionError("robots.txt must not be fetched when the check is disabled")

        monkeypatch.setattr(module, "robots_allow", _explode)

        assert asyncio.run(module.scrape_lead("https://example.com")).company_name == "Muster GmbH"


class TestSearch:
    def test_returns_leads_and_considered_urls(self, monkeypatch):
        graphs = _graphs_stub(SearchGraph=FakeGraph)
        module, _ = _load(monkeypatch, graphs_module=graphs)
        FakeGraph.answer = {"leads": [{"company_name": "Muster GmbH"}]}

        result = asyncio.run(module.search_leads("Coiffeur Zürich", max_results=5))

        assert [lead.company_name for lead in result.leads] == ["Muster GmbH"]
        assert result.considered_urls == ["https://example.com/impressum"]
        assert FakeGraph.calls[0]["config"]["max_results"] == 5

    def test_max_results_falls_back_to_settings(self, monkeypatch):
        graphs = _graphs_stub(SearchGraph=FakeGraph)
        module, _ = _load(monkeypatch, graphs_module=graphs)
        FakeGraph.answer = {"leads": []}

        asyncio.run(module.search_leads("Coiffeur Zürich"))

        assert FakeGraph.calls[0]["config"]["max_results"] == 3
