from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from contracts import clients
from contracts.models import ApiCall, Contract

from .helpers import day

API_PAGE = {
    "totalRecords": 2,
    "opportunitiesData": [
        {"noticeId": "a1", "title": "Mow lawns", "fullParentPathName": "AGRICULTURE.FOREST SERVICE.R9",
         "type": "Solicitation", "typeOfSetAside": "SBA", "responseDeadLine": day(12) + "T17:00:00-05:00",
         "naicsCode": "561730", "active": "Yes", "uiLink": "https://sam.gov/opp/a1/view",
         "placeOfPerformance": {"city": {"name": "Marion"}, "state": {"code": "IL"}, "zip": "62959"},
         "description": "https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=a1"},
        {"noticeId": "a2", "title": "Award for paint", "type": "Award Notice", "active": "Yes",
         "responseDeadLine": day(12) + "T17:00:00-05:00"},
    ],
}


@override_settings(SAM_API_KEY="test", SAM_DAILY_CALL_CAP=3)
class SamCapTests(TestCase):
    def test_calls_stop_at_cap(self):
        for _ in range(3):
            ApiCall.objects.create(source="sam", endpoint="x")
        with self.assertRaises(clients.ApiError):
            clients.sam_get("https://api.sam.gov/x")

    def test_other_sources_do_not_count(self):
        ApiCall.objects.create(source="groq", endpoint="x")
        self.assertEqual(clients.sam_calls_left(), 3)

    @override_settings(SAM_API_KEY="")
    def test_no_key(self):
        with self.assertRaises(clients.ApiError):
            clients.sam_get("https://api.sam.gov/x")

    def test_key_not_logged(self):
        with patch.object(clients, "urlopen") as fake:
            fake.return_value.__enter__.return_value.read.return_value = b"{}"
            clients.sam_get("https://api.sam.gov/x", {"limit": 1})
        self.assertNotIn("test", ApiCall.objects.get().endpoint)

    def test_fetch_new_saves_open_notices(self):
        with patch.object(clients, "search_notices", return_value=API_PAGE):
            call_command("fetch_new", stdout=StringIO())
        self.assertEqual(list(Contract.objects.values_list("notice_id", flat=True)), ["a1"])
        self.assertEqual(Contract.objects.get().agency.sub_tier, "FOREST SERVICE")

    def test_fetch_new_keeps_saved_description(self):
        with patch.object(clients, "search_notices", return_value=API_PAGE):
            call_command("fetch_new", stdout=StringIO())
        Contract.objects.filter(notice_id="a1").update(description_text="Full text here")
        with patch.object(clients, "search_notices", return_value=API_PAGE):
            call_command("fetch_new", stdout=StringIO())
        self.assertEqual(Contract.objects.get(notice_id="a1").description_text, "Full text here")
