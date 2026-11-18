from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contracts import geo
from contracts.filters import filter_contracts, midnight
from core.templatetags.bb import urgency_rgb, urgency_style
from matches.models import ContractorProfile

from .helpers import make_contract


class GeoTests(TestCase):
    def test_zip_lookup(self):
        lat, lon = geo.locate("61820")
        self.assertAlmostEqual(lat, 40.11, places=1)
        self.assertAlmostEqual(lon, -88.24, places=1)

    def test_city_fallback(self):
        self.assertIsNotNone(geo.locate("", "Clarksburg", "WV"))

    def test_unknown_place(self):
        self.assertIsNone(geo.locate("00000", "Nowhere", "ZZ"))

    def test_miles(self):
        champaign, clarksburg = geo.locate("61820"), geo.locate("26301")
        self.assertTrue(400 < geo.miles_between(champaign, clarksburg) < 450)
        self.assertIsNone(geo.miles_between(champaign, None))


class UrgencyTests(TestCase):
    def test_colors_slide_from_red_to_green(self):
        self.assertEqual(urgency_rgb(0), (217, 45, 32))
        self.assertEqual(urgency_rgb(21), (47, 154, 92))
        self.assertEqual(urgency_rgb(40), urgency_rgb(21))
        r3, g3, _ = urgency_rgb(3)
        r10, g10, _ = urgency_rgb(10)
        self.assertGreater(g10, g3)

    def test_style_has_three_colors(self):
        self.assertEqual(urgency_style(5).count("rgb("), 3)

    def test_bands_do_not_overlap(self):
        for d in (2, 5, 10, 30):
            make_contract(f"j{d}", f"Job {d}", due_days=d)
        ids = {key: set(filter_contracts({"when": key}).values_list("notice_id", flat=True))
               for key in ("today", "week", "next", "later")}
        self.assertEqual(ids["week"], {"j2", "j5"})
        self.assertEqual(ids["next"], {"j10"})
        self.assertEqual(ids["later"], {"j30"})

    def test_closing_today_shows_hours(self):
        due = midnight(1) - timedelta(minutes=1)
        job = make_contract("t1", "Closing soon", due_days=0)
        job.due_date = due
        job.save()
        self.assertEqual(job.days_left, 0)
        hours, unit = job.time_left
        self.assertIn(unit, ("hr", "hrs"))
        response = self.client.get(reverse("contracts:list"), {"when": "today"}, HTTP_X_PARTIAL="1")
        self.assertContains(response, "Closing soon")
        self.assertContains(response, "Under a day left")
        response = self.client.get(reverse("contracts:list"), {"when": "week"}, HTTP_X_PARTIAL="1")
        self.assertNotContains(response, "Closing soon")


class BrowsePageTests(TestCase):
    def setUp(self):
        self.il = make_contract("il1", "Roof repair", state="IL", city="PEORIA", due_days=2,
                                lat=40.69, lon=-89.59, place_zip="61604")
        self.il2 = make_contract("il2", "Women-owned cleaning", naics="561720", state="IL", set_aside="WOSB", due_days=9)
        self.tx = make_contract("tx1", "Texas roof", state="TX", due_days=20)

    def test_home_is_the_map_page(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Where do you want to work?")
        self.assertEqual(response.context["state_counts"], {"IL": 2, "TX": 1})

    def test_state_list_has_counts(self):
        states = {s["code"]: s["count"] for s in self.client.get(reverse("core:home")).context["states"]}
        self.assertEqual(states["IL"], 2)
        self.assertEqual(states["WY"], 0)

    def test_pick_several_states(self):
        response = self.client.get(reverse("contracts:list"), {"state": ["IL", "TX"]}, HTTP_X_PARTIAL="1")
        self.assertContains(response, "Roof repair")
        self.assertContains(response, "Texas roof")
        response = self.client.get(reverse("contracts:list"), {"state": ["TX"]}, HTTP_X_PARTIAL="1")
        self.assertNotContains(response, "Roof repair")

    def test_partial_is_grouped_by_urgency(self):
        response = self.client.get(reverse("contracts:list"), HTTP_X_PARTIAL="1")
        self.assertContains(response, "This week")
        self.assertContains(response, "Later")
        self.assertContains(response, 'data-count="3"')

    def test_rows_carry_map_points(self):
        response = self.client.get(reverse("contracts:list"), HTTP_X_PARTIAL="1")
        self.assertContains(response, 'data-lat="40.69"')

    def test_distance_and_can_bid_for_logged_in_user(self):
        user = User.objects.create_user("roofer", password="tin-roof-2026")
        ContractorProfile.objects.create(user=user, trades=["roofing"], states=["IL"], zip_code="61820")
        self.client.login(username="roofer", password="tin-roof-2026")
        response = self.client.get(reverse("contracts:list"), {"state": "IL"}, HTTP_X_PARTIAL="1")
        self.assertContains(response, "mi away")
        self.assertContains(response, "You can bid")
        self.assertContains(response, "Woman-owned only")

    def test_only_jobs_i_can_bid_on(self):
        user = User.objects.create_user("roofer", password="tin-roof-2026")
        ContractorProfile.objects.create(user=user, trades=["roofing"], states=["IL"])
        self.client.login(username="roofer", password="tin-roof-2026")
        response = self.client.get(reverse("contracts:list"), {"can_bid": "1"}, HTTP_X_PARTIAL="1")
        self.assertContains(response, "Roof repair")
        self.assertNotContains(response, "Women-owned cleaning")

    def test_can_bid_filter_ignored_without_profile(self):
        response = self.client.get(reverse("contracts:list"), {"can_bid": "1"}, HTTP_X_PARTIAL="1")
        self.assertContains(response, "Women-owned cleaning")

    def test_panel_partial(self):
        response = self.client.get(reverse("contracts:detail", args=["il1"]), {"panel": "1"})
        self.assertContains(response, "Bid on SAM.gov")
        self.assertContains(response, "js-close")
        self.assertNotContains(response, "<html")

    def test_full_detail_page_still_works(self):
        response = self.client.get(reverse("contracts:detail", args=["il1"]))
        self.assertContains(response, "<html")
        self.assertContains(response, "Bids due")
