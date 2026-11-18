from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.filters import filter_contracts
from contracts.models import Contract

from .helpers import make_contract


class FilterTests(TestCase):
    def setUp(self):
        self.roof = make_contract("r1", "Roof repair", naics="238160", state="IL", set_aside="SBA", due_days=20)
        self.clean = make_contract("c1", "Janitorial services", naics="561720", state="IL", set_aside="", due_days=5)
        self.hvac = make_contract("h1", "HVAC repair", naics="238220", state="TX", set_aside="SDVOSBC", due_days=40,
                                  posted_days=-1)
        self.closed = make_contract("old", "Old roof job", due_days=-2)

    def ids(self, params):
        return [c.notice_id for c in filter_contracts(params)]

    def test_past_due_not_shown(self):
        self.assertNotIn("old", self.ids({}))

    def test_default_sort_is_due_soonest(self):
        self.assertEqual(self.ids({}), ["c1", "r1", "h1"])

    def test_sort_newest(self):
        self.assertEqual(self.ids({"sort": "new"})[0], "h1")

    def test_sort_most_time_left(self):
        self.assertEqual(self.ids({"sort": "days"})[0], "h1")

    def test_keyword(self):
        self.assertEqual(self.ids({"q": "roof"}), ["r1"])

    def test_keyword_searches_description(self):
        make_contract("d1", "Building 9 work", text="Replace shingles and gutters")
        self.assertEqual(self.ids({"q": "shingles"}), ["d1"])

    def test_trade(self):
        self.assertEqual(self.ids({"trade": "janitorial"}), ["c1"])

    def test_state(self):
        self.assertEqual(self.ids({"state": "tx"}), ["h1"])

    def test_set_aside_groups(self):
        self.assertEqual(self.ids({"set_aside": "small"}), ["r1"])
        self.assertEqual(self.ids({"set_aside": "sdvosb"}), ["h1"])
        self.assertEqual(self.ids({"set_aside": "none"}), ["c1"])

    def test_due_within(self):
        self.assertEqual(self.ids({"due_within": "7"}), ["c1"])

    def test_bad_values_are_ignored(self):
        self.assertEqual(len(self.ids({"trade": "nope", "state": "ZZ", "sort": "x", "due_within": "abc"})), 3)


class PageTests(TestCase):
    def setUp(self):
        self.contract = make_contract("r1", "Roof repair at Peoria", text="Tear off and replace the roof.")

    def test_home(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Roof repair at Peoria")

    def test_list_page_filters(self):
        make_contract("c1", "Janitorial services", naics="561720")
        response = self.client.get(reverse("contracts:list"), {"trade": "roofing"})
        self.assertContains(response, "Roof repair at Peoria")
        self.assertNotContains(response, "Janitorial services")

    def test_one_band_paginates(self):
        for i in range(45):
            make_contract(f"x{i}", f"Extra job {i}", due_days=3)
        response = self.client.get(reverse("contracts:list"), {"when": "week"})
        self.assertEqual(len(response.context["contracts"]), 40)
        self.assertContains(response, "Page 1 of 2")

    def test_overview_shows_a_few_per_band(self):
        for i in range(45):
            make_contract(f"x{i}", f"Extra job {i}", due_days=3)
        response = self.client.get(reverse("contracts:list"), HTTP_X_PARTIAL="1")
        week = [g for g in response.context["groups"] if g["key"] == "week"][0]
        self.assertEqual(len(week["items"]), 5)
        self.assertEqual(week["count"], 45)
        self.assertContains(response, "See all 45 due this week")
        self.assertNotContains(response, "Page 1 of")

    def test_detail_page(self):
        response = self.client.get(reverse("contracts:detail", args=["r1"]))
        self.assertContains(response, "Tear off and replace the roof.")
        self.assertContains(response, "Bid on SAM.gov")
        self.assertContains(response, "Roofing")

    def test_calendar_file(self):
        response = self.client.get(reverse("contracts:calendar", args=["r1"]))
        self.assertEqual(response["Content-Type"], "text/calendar")
        self.assertIn("SUMMARY:Bid due: Roof repair at Peoria", response.content.decode())

    def test_filters_are_kept_on_the_page(self):
        response = self.client.get(reverse("contracts:list"), {"trade": "roofing", "state": "IL"})
        self.assertContains(response, '<option value="roofing" selected>')
        self.assertEqual(response.context["picked"], ["IL"])

    def test_detail_404(self):
        self.assertEqual(self.client.get(reverse("contracts:detail", args=["nope"])).status_code, 404)

    def test_about(self):
        self.assertContains(self.client.get(reverse("core:about")), "Set-aside")


class ApiTests(TestCase):
    def setUp(self):
        make_contract("r1", "Roof repair", state="IL")
        make_contract("h1", "HVAC repair", naics="238220", state="TX")

    def test_list(self):
        data = self.client.get(reverse("api:contracts")).json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["results"][0]["notice_id"], "r1")

    def test_list_filters_and_limit(self):
        data = self.client.get(reverse("api:contracts"), {"state": "TX", "limit": 1}).json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["trade"], "Plumbing, heating, and cooling")

    def test_bad_limit(self):
        self.assertEqual(self.client.get(reverse("api:contracts"), {"limit": "lots"}).status_code, 400)

    def test_detail(self):
        data = self.client.get(reverse("api:contract", args=["r1"])).json()
        self.assertEqual(data["title"], "Roof repair")
        self.assertIn("description", data)


class SeedDemoTests(TestCase):
    def test_seed_and_clear(self):
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Contract.objects.filter(is_demo=True).count(), 30)
        self.assertTrue(all(c.due_date > timezone.now() - timedelta(minutes=1) for c in Contract.objects.all()))
        call_command("seed_demo", "--clear", stdout=StringIO())
        self.assertEqual(Contract.objects.count(), 0)


class BidLinkTests(TestCase):
    """Bid on SAM.gov must open the exact posting. Demo jobs have no posting, so no link."""

    def test_real_job_links_to_exact_notice(self):
        c = make_contract("ff3c2850ffbc46dc96d42b5fa963540d", "Window cleaning")
        self.assertEqual(c.bid_url, "https://sam.gov/opp/ff3c2850ffbc46dc96d42b5fa963540d/view")
        response = self.client.get(c.get_absolute_url())
        self.assertContains(response, 'href="https://sam.gov/opp/ff3c2850ffbc46dc96d42b5fa963540d/view"')

    def test_every_list_card_has_bid_link(self):
        make_contract("a1", "Job A")
        make_contract("b2", "Job B")
        response = self.client.get(reverse("contracts:list"))
        self.assertContains(response, "https://sam.gov/opp/a1/view")
        self.assertContains(response, "https://sam.gov/opp/b2/view")

    def test_demo_job_has_no_sam_link(self):
        c = make_contract("DEMO0001", "Demo roof", is_demo=True)
        self.assertEqual(c.bid_url, "")
        response = self.client.get(c.get_absolute_url())
        self.assertNotContains(response, "sam.gov/opp/DEMO0001")
        self.assertContains(response, "Demo job")

    def test_api_gives_exact_link(self):
        make_contract("a1", "Job A")
        data = self.client.get(reverse("api:contract", args=["a1"])).json()
        self.assertEqual(data["sam_url"], "https://sam.gov/opp/a1/view")

    def test_bid_click_is_counted(self):
        from contracts.models import BidClick
        make_contract("a1", "Job A")
        response = self.client.post(reverse("contracts:bid_click", args=["a1"]), {"page": "contracts:list"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BidClick.objects.get().page, "contracts:list")


class FastSearchTests(TestCase):
    def setUp(self):
        make_contract("r1", "Roof repair")
        make_contract("c1", "Janitorial services", naics="561720")

    def test_partial_results_only(self):
        response = self.client.get(reverse("contracts:list"), {"q": "roof"}, HTTP_X_PARTIAL="1")
        self.assertContains(response, "Roof repair")
        self.assertNotContains(response, "<html")

    def test_last_search_remembered(self):
        self.client.get(reverse("contracts:list"), {"trade": "roofing", "page": "1"})
        response = self.client.get(reverse("core:about"))
        self.assertContains(response, 'href="/contracts/?trade=roofing"')
