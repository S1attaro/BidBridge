from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contracts.tests.helpers import make_contract

from .models import SavedContract


class SavedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("roofer", password="tin-roof-2026")
        self.other = User.objects.create_user("cleaner", password="mop-bucket-2026")
        self.contract = make_contract("r1", "Roof repair")
        self.client.login(username="roofer", password="tin-roof-2026")

    def test_save_and_unsave(self):
        url = reverse("saved:toggle", args=["r1"])
        self.client.post(url)
        self.assertTrue(SavedContract.objects.filter(user=self.user, contract=self.contract).exists())
        self.client.post(url)
        self.assertFalse(SavedContract.objects.exists())

    def test_list_shows_only_my_jobs(self):
        other_job = make_contract("c1", "Cleaning job")
        SavedContract.objects.create(user=self.user, contract=self.contract)
        SavedContract.objects.create(user=self.other, contract=other_job)
        response = self.client.get(reverse("saved:list"))
        self.assertContains(response, "Roof repair")
        self.assertNotContains(response, "Cleaning job")

    def test_update_status_and_note(self):
        s = SavedContract.objects.create(user=self.user, contract=self.contract)
        self.client.post(reverse("saved:edit", args=[s.pk]), {"status": "bidding", "note": "Site visit Monday"})
        s.refresh_from_db()
        self.assertEqual((s.status, s.note), ("bidding", "Site visit Monday"))

    def test_bad_status_rejected(self):
        s = SavedContract.objects.create(user=self.user, contract=self.contract)
        response = self.client.post(reverse("saved:edit", args=[s.pk]), {"status": "maybe", "note": ""})
        self.assertEqual(response.status_code, 200)
        s.refresh_from_db()
        self.assertEqual(s.status, "thinking")

    def test_cannot_edit_or_delete_someone_elses(self):
        theirs = SavedContract.objects.create(user=self.other, contract=self.contract)
        self.assertEqual(self.client.get(reverse("saved:edit", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("saved:delete", args=[theirs.pk])).status_code, 404)
        self.assertTrue(SavedContract.objects.filter(pk=theirs.pk).exists())

    def test_delete(self):
        s = SavedContract.objects.create(user=self.user, contract=self.contract)
        self.client.post(reverse("saved:delete", args=[s.pk]))
        self.assertFalse(SavedContract.objects.exists())

    def test_must_log_in(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("saved:list")), reverse("login") + "?next=" + reverse("saved:list"))
        self.client.post(reverse("saved:toggle", args=["r1"]))
        self.assertFalse(SavedContract.objects.exists())

    def test_toggle_ignores_outside_next_url(self):
        response = self.client.post(reverse("saved:toggle", args=["r1"]), {"next": "https://evil.example.com/"})
        self.assertRedirects(response, self.contract.get_absolute_url(), fetch_redirect_response=False)

    def test_detail_page_shows_saved(self):
        SavedContract.objects.create(user=self.user, contract=self.contract)
        self.assertContains(self.client.get(self.contract.get_absolute_url()), "Saved")

    def test_save_without_reload_returns_json(self):
        url = reverse("saved:toggle", args=["r1"])
        self.assertEqual(self.client.post(url, HTTP_X_REQUESTED_WITH="fetch").json(), {"saved": True})
        self.assertEqual(self.client.post(url, HTTP_X_REQUESTED_WITH="fetch").json(), {"saved": False})

    def test_list_page_shows_filled_save_button(self):
        SavedContract.objects.create(user=self.user, contract=self.contract)
        self.assertContains(self.client.get(reverse("contracts:list")), 'aria-pressed="true"')
