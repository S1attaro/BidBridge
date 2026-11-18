from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AccountTests(TestCase):
    def test_signup_logs_in(self):
        response = self.client.post(reverse("core:signup"), {
            "username": "roofer1", "password": "tin-roof-2026",
        })
        self.assertRedirects(response, reverse("matches:profile"))
        self.assertTrue(User.objects.filter(username="roofer1").exists())
        self.assertEqual(self.client.get(reverse("core:home")).context["user"].username, "roofer1")

    def test_signup_bad_password(self):
        response = self.client.post(reverse("core:signup"), {
            "username": "roofer1", "password": "123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_login_and_logout(self):
        User.objects.create_user("roofer1", password="tin-roof-2026")
        self.client.post(reverse("login"), {"username": "roofer1", "password": "tin-roof-2026"})
        self.assertContains(self.client.get(reverse("core:home")), "Log out")
        self.client.post(reverse("logout"))
        self.assertContains(self.client.get(reverse("core:home")), "Get started")
