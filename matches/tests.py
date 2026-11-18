from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contracts.tests.helpers import make_contract

from .matching import refresh_matches, score_contracts
from .models import ContractorProfile, Match


class MatchingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("roofer", password="tin-roof-2026")
        self.profile = ContractorProfile.objects.create(
            user=self.user, trades=["roofing"], services="metal roofs, gutters, shingles", states=["IL"],
        )
        self.roof = make_contract("r1", "Roof replacement", naics="238160", state="IL", city="PEORIA", set_aside="SBA",
                                  due_days=20)
        self.gutter = make_contract("g1", "Building repairs including gutters and shingles", naics="236220", state="IL",
                                    set_aside="", due_days=15)
        self.texas_roof = make_contract("t1", "Roof repair", naics="238160", state="TX")
        self.wosb_roof = make_contract("w1", "Roof repair for women-owned", naics="238160", state="IL", set_aside="WOSB")
        self.cleaning = make_contract("c1", "Janitorial services", naics="561720", state="IL", set_aside="")

    def ids(self):
        return [c.notice_id for _, _, c, _ in score_contracts(self.profile)]

    def test_trade_match_ranks_first(self):
        self.assertEqual(self.ids()[0], "r1")

    def test_keyword_overlap_without_trade_code(self):
        self.assertIn("g1", self.ids())

    def test_other_states_left_out(self):
        self.assertNotIn("t1", self.ids())
        self.profile.states = ["IL", "TX"]
        self.assertIn("t1", self.ids())

    def test_set_aside_rules(self):
        self.assertNotIn("w1", self.ids())
        self.profile.set_asides = ["wosb"]
        self.assertIn("w1", self.ids())

    def test_not_small_cant_see_small_business_jobs(self):
        self.profile.is_small = False
        self.assertNotIn("r1", self.ids())

    def test_unrelated_work_left_out(self):
        self.assertNotIn("c1", self.ids())

    def test_reason_sentence(self):
        reason = dict((c.notice_id, r) for _, _, c, r in score_contracts(self.profile))["r1"]
        self.assertEqual(reason, "Your kind of work in Peoria, IL. Only for small businesses.")

    def test_refresh_replaces_matches(self):
        refresh_matches(self.profile)
        refresh_matches(self.profile)
        self.assertEqual(Match.objects.filter(contract=self.roof).count(), 1)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("roofer", password="tin-roof-2026")
        self.client.login(username="roofer", password="tin-roof-2026")
        make_contract("r1", "Roof replacement", naics="238160", state="IL")

    def post_profile(self, **changes):
        data = {"trades": ["roofing"], "services": "metal roofs", "states": ["IL"], "zip_code": "61820",
                "is_small": "on", **changes}
        return self.client.post(reverse("matches:profile"), data)

    def test_create_profile_and_see_matches(self):
        response = self.post_profile()
        self.assertRedirects(response, reverse("matches:list"))
        self.assertContains(self.client.get(reverse("matches:list")), "Roof replacement")

    def test_must_pick_a_trade(self):
        response = self.post_profile(trades=[])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContractorProfile.objects.exists())

    def test_must_pick_a_state(self):
        response = self.post_profile(states=[])
        self.assertContains(response, "Pick at least one state.")
        self.assertFalse(ContractorProfile.objects.exists())

    def test_bad_zip(self):
        response = self.post_profile(zip_code="6182")
        self.assertContains(response, "A ZIP code is 5 numbers")

    def test_edit_keeps_one_profile(self):
        self.post_profile()
        self.post_profile(services="gutters")
        self.assertEqual(ContractorProfile.objects.get().services, "gutters")

    def test_no_profile_redirects_to_form(self):
        self.assertRedirects(self.client.get(reverse("matches:list")), reverse("matches:profile"))

    def test_matches_page_shows_reason(self):
        self.post_profile()
        self.assertContains(self.client.get(reverse("matches:list")), "Your kind of work in Peoria, IL.")

    def test_must_log_in(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("matches:profile")).status_code, 302)
        self.assertEqual(self.client.get(reverse("matches:list")).status_code, 302)

    def test_users_only_see_their_own_matches(self):
        self.post_profile()
        other = User.objects.create_user("cleaner", password="mop-bucket-2026")
        ContractorProfile.objects.create(user=other, trades=["janitorial"], states=["TX"])
        self.client.login(username="cleaner", password="mop-bucket-2026")
        self.assertNotContains(self.client.get(reverse("matches:list")), "Roof replacement")


class AlertTests(TestCase):
    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        self.user = User.objects.create_user("roofer2", password="tin-roof-2026", email="r@example.com")
        self.profile = ContractorProfile.objects.create(
            user=self.user, trades=["roofing"], states=["IL"], alerts_on=True, alert_email="r@example.com",
            last_alert_at=timezone.now() - timedelta(hours=1),
        )

    def send(self):
        from io import StringIO
        from django.core.management import call_command
        call_command("send_alerts", stdout=StringIO())

    def test_new_matching_job_is_emailed(self):
        from django.core import mail
        make_contract("n1", "Roof replacement", naics="238160", state="IL", due_days=10)
        self.send()
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["r@example.com"])
        self.assertIn("1 new job for you", email.subject)
        self.assertIn("Roof replacement", email.body)
        self.assertIn(str(self.profile.alert_token), email.body)

    def test_nothing_new_means_no_email(self):
        from django.core import mail
        make_contract("n1", "Roof replacement", naics="238160", state="IL", due_days=10)
        self.send()
        self.send()
        self.assertEqual(len(mail.outbox), 1)

    def test_skips_other_states_closing_soon_and_alerts_off(self):
        from django.core import mail
        make_contract("tx", "Roof replacement", naics="238160", state="TX", due_days=10)
        make_contract("soon", "Roof patch", naics="238160", state="IL", due_days=1)
        self.send()
        self.assertEqual(len(mail.outbox), 0)
        self.profile.alerts_on = False
        self.profile.save()
        make_contract("n2", "Roof replacement", naics="238160", state="IL", due_days=10)
        self.send()
        self.assertEqual(len(mail.outbox), 0)

    def test_stop_link_asks_then_turns_off(self):
        url = reverse("matches:alerts_off", args=[self.profile.alert_token])
        self.assertContains(self.client.get(url), "Stop job emails?")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.alerts_on)
        self.assertContains(self.client.post(url), "Emails stopped")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.alerts_on)

    def test_alerts_need_an_email(self):
        from .forms import ProfileForm
        form = ProfileForm({"trades": ["roofing"], "states": ["IL"], "alerts_on": "on", "alert_email": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("alert_email", form.errors)

    def test_each_profile_gets_its_own_token(self):
        other = User.objects.create_user("b", password="tin-roof-2026")
        p2 = ContractorProfile.objects.create(user=other, trades=["roofing"], states=["IL"])
        self.assertNotEqual(self.profile.alert_token, p2.alert_token)
