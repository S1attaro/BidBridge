import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from contracts.clients import ApiError
from contracts.models import ApiCall
from contracts.tests.helpers import make_contract

from . import ai
from .models import AIRequestLog, ContractSummary

TEXT = ("The contractor shall remove and replace 14,000 square feet of roofing on Building 12. "
        "Contractor must hold a roofing license. A site visit will be held. Work must be done in 90 days. "
        "Questions to jane.doe@army.mil or (217) 555-0142.")

GOOD = {
    "summary": "The Army needs a new roof on Building 12. It is about 14,000 square feet. You must finish in 90 days.",
    "job": "Replace roof on one building",
    "requirements": ["Roofing license", "Go to the site visit", "Finish in 90 days"],
    "skills": ["roofing"],
}


def groq_reply(payload, usage=None):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return {"choices": [{"message": {"content": content}}], "usage": usage or {"prompt_tokens": 400, "completion_tokens": 80}}


@override_settings(GROQ_API_KEY="test")
class SummaryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.contract = make_contract("r1", "Roof Replacement, Building 12", text=TEXT)

    def test_ai_summary_saved(self):
        with patch.object(ai.clients, "post_json", return_value=groq_reply(GOOD)):
            summary = ai.summarize(self.contract)
        self.assertEqual(summary.source, "ai")
        self.assertEqual(summary.job, "Replace roof on one building")
        self.assertEqual(len(summary.requirements), 3)
        self.assertTrue(summary.used_full_text)
        self.assertIsNotNone(summary.reading_grade)

    def test_email_and_phone_not_sent(self):
        with patch.object(ai.clients, "post_json", return_value=groq_reply(GOOD)) as fake:
            ai.summarize(self.contract)
        sent = fake.call_args[0][2]["messages"][1]["content"]
        self.assertNotIn("jane.doe", sent)
        self.assertNotIn("555-0142", sent)
        self.assertIn("[email]", sent)

    def test_made_up_numbers_dropped(self):
        bad = {**GOOD, "summary": "The Army needs a new roof. The budget is $250,000.",
               "requirements": ["Roofing license", "Bond of 50,000 dollars"]}
        with patch.object(ai.clients, "post_json", return_value=groq_reply(bad)):
            summary = ai.summarize(self.contract)
        self.assertNotIn("250,000", summary.summary)
        self.assertEqual(summary.requirements, ["Roofing license"])
        self.assertTrue(summary.warnings)

    def test_groq_down_falls_back_to_simple(self):
        with patch.object(ai.clients, "post_json", side_effect=ApiError("down", status=503)):
            summary = ai.summarize(self.contract)
        self.assertEqual(summary.source, "simple")
        self.assertIn("roofing", summary.summary)
        self.assertIn("Contractor must hold a roofing license.", summary.requirements)

    def test_not_json_falls_back(self):
        with patch.object(ai.clients, "post_json", return_value=groq_reply("Sorry, I can't help.")):
            summary = ai.summarize(self.contract)
        self.assertEqual(summary.source, "simple")
        self.assertFalse(AIRequestLog.objects.get().ok)

    def test_empty_summary_falls_back(self):
        with patch.object(ai.clients, "post_json", return_value=groq_reply({**GOOD, "summary": "It costs 999 dollars."})):
            summary = ai.summarize(self.contract)
        self.assertEqual(summary.source, "simple")

    @override_settings(GROQ_API_KEY="")
    def test_no_key_uses_simple(self):
        self.assertEqual(ai.summarize(self.contract).source, "simple")

    def test_request_logged_with_tokens(self):
        with patch.object(ai.clients, "post_json", return_value=groq_reply(GOOD)):
            ai.summarize(self.contract)
        row = AIRequestLog.objects.get()
        self.assertEqual((row.prompt_tokens, row.completion_tokens, row.ok), (400, 80, True))

    def test_summarize_twice_updates(self):
        with patch.object(ai.clients, "post_json", return_value=groq_reply(GOOD)):
            ai.summarize(self.contract)
            ai.summarize(self.contract)
        self.assertEqual(ContractSummary.objects.count(), 1)

    @override_settings(SAM_API_KEY="test", SAM_DAILY_CALL_CAP=8)
    def test_fetches_missing_text_when_allowed(self):
        c = make_contract("r2", "Roof job", description_url="https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=r2")
        with patch.object(ai.clients, "fetch_description", return_value="Fix the roof. Must have a license.") as fetch, \
                patch.object(ai.clients, "post_json", return_value=groq_reply(GOOD)):
            ai.summarize(c, allow_fetch=True)
        fetch.assert_called_once()
        c.refresh_from_db()
        self.assertTrue(c.description_fetched)

    @override_settings(SAM_API_KEY="test", SAM_DAILY_CALL_CAP=3)
    def test_no_fetch_when_few_sam_calls_left(self):
        ApiCall.objects.create(source="sam", endpoint="x")
        c = make_contract("r2", "Roof job", description_url="https://api.sam.gov/x")
        with patch.object(ai.clients, "fetch_description") as fetch, \
                patch.object(ai.clients, "post_json", return_value=groq_reply(GOOD)):
            summary = ai.summarize(c, allow_fetch=True)
        fetch.assert_not_called()
        self.assertFalse(summary.used_full_text)

    def test_reading_grade(self):
        easy = ai.reading_grade("The Army needs a new roof. You must have a license. Bids are due soon.")
        hard = ai.reading_grade("The contractor shall furnish all requisite materials, comprehensive labor, "
                                "and supervisory personnel necessary for the rehabilitation of facilities.")
        self.assertLess(easy, hard)

    def test_view_makes_summary_once(self):
        url = reverse("summaries:make", args=["r1"])
        with patch.object(ai.clients, "post_json", return_value=groq_reply(GOOD)) as fake:
            first = self.client.post(url)
            self.client.post(url)
        self.assertContains(first, "Replace roof on one building")
        self.assertEqual(fake.call_count, 1)

    def test_view_rate_limit_gives_simple(self):
        with patch("summaries.views.HOURLY_LIMIT", 0), patch.object(ai.clients, "post_json") as fake:
            response = self.client.post(reverse("summaries:make", args=["r1"]))
        fake.assert_not_called()
        self.assertContains(response, "Basic summary")

    def test_view_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse("summaries:make", args=["r1"])).status_code, 405)


class KeyDateTests(TestCase):
    def test_real_dates_kept_and_made_up_dates_dropped(self):
        source = "Site visit on Nov 30, 2026 at 9:00 AM. Questions are due Nov 24."
        warnings = []
        kept = ai.check_dates([
            {"what": "Site visit", "when": "Nov 30, 2026 at 9:00 AM"},
            {"what": "Questions due", "when": "Nov 24"},
            {"what": "Pre-bid meeting", "when": "Dec 2"},
            {"what": "Nothing", "when": "soon"},
            "junk",
        ], source, warnings)
        self.assertEqual([k["what"] for k in kept], ["Site visit", "Questions due"])
        self.assertTrue(warnings)

    def test_not_a_list(self):
        self.assertEqual(ai.check_dates("Nov 30", "Nov 30", []), [])
