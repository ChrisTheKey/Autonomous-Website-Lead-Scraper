"""Tests for the crawl -> analysis task chain. No database, no broker.

_crawl_company and _analyse_website are async, so patch() replaces them with an
AsyncMock: a plain return value is what the awaited call resolves to.
"""

from unittest.mock import patch

import pytest

from app.workers.tasks import celery_app, crawl_company_task


class TestCrawlTriggersAnalysis:
    @patch("app.workers.tasks.analyse_website_task")
    @patch("app.workers.tasks._crawl_company")
    def test_successful_crawl_dispatches_analysis_once(self, mock_crawl, mock_analyse):
        mock_crawl.side_effect = lambda cid: {"company_id": cid, "pages_crawled": 4}
        result = crawl_company_task(7)
        mock_analyse.delay.assert_called_once_with(7)
        assert result["pages_crawled"] == 4

    @patch("app.workers.tasks.analyse_website_task")
    @patch("app.workers.tasks._crawl_company")
    def test_dispatch_passes_the_crawled_company_id(self, mock_crawl, mock_analyse):
        mock_crawl.side_effect = lambda cid: {"company_id": cid, "pages_crawled": 1}
        crawl_company_task(4242)
        mock_analyse.delay.assert_called_once_with(4242)

    @patch("app.workers.tasks.analyse_website_task")
    @patch("app.workers.tasks._crawl_company")
    def test_company_without_website_does_not_dispatch(self, mock_crawl, mock_analyse):
        mock_crawl.side_effect = lambda cid: {"error": "no_website"}
        result = crawl_company_task(7)
        mock_analyse.delay.assert_not_called()
        assert result["error"] == "no_website"

    @patch("app.workers.tasks.analyse_website_task")
    @patch("app.workers.tasks._crawl_company")
    def test_failing_crawl_does_not_dispatch(self, mock_crawl, mock_analyse):
        mock_crawl.side_effect = RuntimeError("crawl exploded")
        with pytest.raises(RuntimeError):
            crawl_company_task(7)
        mock_analyse.delay.assert_not_called()

    @patch("app.workers.tasks.analyse_website_task")
    @patch("app.workers.tasks._crawl_company")
    def test_crawl_without_reachable_pages_still_dispatches(self, mock_crawl, mock_analyse):
        # An unreachable site is itself a weakness the analysis is meant to record.
        mock_crawl.side_effect = lambda cid: {"company_id": cid, "pages_crawled": 0}
        crawl_company_task(9)
        mock_analyse.delay.assert_called_once_with(9)

    @patch("app.workers.tasks.analyse_website_task")
    @patch("app.workers.tasks._crawl_company")
    def test_each_crawl_dispatches_exactly_one_analysis(self, mock_crawl, mock_analyse):
        mock_crawl.side_effect = lambda cid: {"company_id": cid, "pages_crawled": 2}
        crawl_company_task(1)
        crawl_company_task(2)
        assert mock_analyse.delay.call_count == 2
        assert [c.args[0] for c in mock_analyse.delay.call_args_list] == [1, 2]


class TestChainDoesNotRecurse:
    @patch("app.workers.tasks.crawl_company_task")
    @patch("app.workers.tasks._analyse_website")
    def test_analysis_does_not_dispatch_a_crawl(self, mock_analyse, mock_crawl):
        from app.workers.tasks import analyse_website_task

        mock_analyse.side_effect = lambda cid: {"company_id": cid, "score": 55}
        result = analyse_website_task(7)
        mock_crawl.delay.assert_not_called()
        assert result["score"] == 55


class TestTaskRegistrationUnchanged:
    def test_both_tasks_still_registered(self):
        assert "crawl_company_task" in celery_app.tasks
        assert "analyse_website_task" in celery_app.tasks

    def test_analysis_still_routes_to_analyse_queue(self):
        queue = celery_app.amqp.router.route({}, "analyse_website_task").get("queue")
        assert getattr(queue, "name", queue) == "analyse"

    def test_crawl_still_routes_to_crawl_queue(self):
        queue = celery_app.amqp.router.route({}, "crawl_company_task").get("queue")
        assert getattr(queue, "name", queue) == "crawl"
