from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts import importer
from contracts.cleanup import dupe_key, is_goods, short_title
from contracts.filters import open_contracts
from contracts.models import Agency, Contract

from .helpers import make_contract

# Real SAM.gov titles and what the list should show.
TITLES = [
    ("Combined Synopsis/ Solicitation for Ellsworth AFB Grounds Maintenance - FA469027Q0004", "Ellsworth AFB Grounds Maintenance"),
    ("Amendment 001 - RFQ Number: 19KU2027Q0002- Providing Cooking Services at the Marine Security Guard Residence (MSGR)",
     "Cooking Services at the Marine Security Guard Residence"),
    ("S205--Sources Sought Crown Hill National Cemetery Trash Services", "Crown Hill National Cemetery Trash Services"),
    ("Y1DA--561-26-103 Upgrade Electrical and Plumbing in Building 18B", "Upgrade Electrical and Plumbing in Building 18B"),
    ("PIP-II F-37 BUILDING LWC PUMP ROOM PIPING SYSTEM INSTALLATION", "PIP-II F-37 Building LWC Pump Room Piping System Installation"),
    ("Office Supplies, Blanket Purchase Agreement", "Office Supplies"),
    ("Request for Quotation (RFQ) 19NL8027Q0003 – Hotel Accommodation Services", "Hotel Accommodation Services"),
    ("Notice of Intent to Sole Source Elevator Maintenance", "Sole Source Elevator Maintenance"),
    ("Roof Replacement, Building 12, Scott AFB", "Roof Replacement, Building 12, Scott AFB"),
]


class ShortTitleTests(TestCase):
    def test_real_titles(self):
        for title, expected in TITLES:
            with self.subTest(title=title):
                self.assertEqual(short_title(title), expected)

    def test_never_empty_and_never_too_long(self):
        for title in ["RFQ", "12345678", "", "x" * 300, "A " * 200]:
            result = short_title(title)
            self.assertLessEqual(len(result), 81)
            if title.strip():
                self.assertTrue(result)

    def test_no_em_dashes(self):
        self.assertNotIn("—", short_title("Guard Services — CDC Facilities"))

    def test_long_title_keeps_what_the_work_is(self):
        title = ("Mississippi River, Baton Rouge to Gulf of Mexico, Southwest Pass Maintenance Dredging, "
                 "Cutterhead Dredge No. 2-2025 (OM25276)")
        self.assertNotEqual(short_title(title), "Mississippi River")


class GoodsTests(TestCase):
    def test_product_codes_are_goods(self):
        self.assertTrue(is_goods("5340"))
        self.assertTrue(is_goods("", "53--SEAL RING,METAL"))
        self.assertFalse(is_goods("Z2DA"))
        self.assertFalse(is_goods("", "Roof repair"))

    def test_parts_orders_are_hidden(self):
        make_contract("g1", "Seal ring", psc_code="5340", is_goods=True)
        make_contract("s1", "Roof repair")
        self.assertEqual(list(open_contracts().values_list("notice_id", flat=True)), ["s1"])


class RepeatTests(TestCase):
    def setUp(self):
        self.agency = Agency.objects.create(name="DEPT OF DEFENSE", sub_tier="ARMY", office="W7")

    def job(self, notice_id, sol, posted_days, title="Roof repair"):
        due = timezone.now() + timedelta(days=10)
        c = Contract(notice_id=notice_id, title=title, solicitation_number=sol, agency=self.agency,
                     posted_date=timezone.now() - timedelta(days=posted_days), due_date=due)
        c.tidy().save()
        return c

    def test_only_newest_copy_is_shown(self):
        self.job("old", "W912-26-Q-0001", 9)
        self.job("new", "W912-26-Q-0001", 1)
        self.job("other", "W912-26-Q-0002", 5)
        importer.mark_repeats()
        shown = set(open_contracts().values_list("notice_id", flat=True))
        self.assertEqual(shown, {"new", "other"})

    def test_sol_number_spelling_doesnt_matter(self):
        key1 = dupe_key("W912-26-Q-0001", "ARMY", "a", "", None)
        key2 = dupe_key("w912 26 q 0001", "ARMY", "b", "", None)
        self.assertEqual(key1, key2)

    def test_look_alike_jobs_get_told_apart(self):
        base = "Mississippi River, Baton Rouge to Gulf of Mexico, Southwest Pass Maintenance Dredging, Cutterhead Dredge"
        self.job("d1", "W912P825B0004", 1, title=base + " No. 2-2025")
        self.job("d2", "W912P825B0005", 1, title=base + " No. 3-2025")
        importer.mark_repeats()
        titles = sorted(open_contracts().values_list("short_title", flat=True))
        self.assertEqual(len(set(titles)), 2)
        self.assertTrue(titles[0].endswith("No. 2-2025"))

    def test_repeat_check_runs_after_import(self):
        out = StringIO()
        self.job("old", "SOL-1", 9)
        self.job("new", "SOL-1", 1)
        call_command("fetch_new", max_calls=0, stdout=out, stderr=StringIO())
        self.assertEqual(open_contracts().count(), 1)


class TitleDisplayTests(TestCase):
    def test_list_shows_short_title_and_panel_shows_full(self):
        c = make_contract("t1", "Combined Synopsis/ Solicitation for Ellsworth AFB Grounds Maintenance - FA469027Q0004")
        c.tidy().save()
        page = self.client.get(reverse("contracts:list"), HTTP_X_PARTIAL="1")
        self.assertContains(page, ">Ellsworth AFB Grounds Maintenance<")
        panel = self.client.get(c.get_absolute_url() + "?panel=1")
        self.assertContains(panel, "Ellsworth AFB Grounds Maintenance")
        self.assertContains(panel, "Full title")
        self.assertContains(panel, "FA469027Q0004")


class AgencyNameTests(TestCase):
    def test_backwards_department_names(self):
        self.assertEqual(Agency(name="X", sub_tier="VETERANS AFFAIRS, DEPARTMENT OF").short_name, "Dept of Veterans Affairs")
        self.assertEqual(Agency(name="X", sub_tier="DEPT OF THE ARMY").short_name, "Dept of the Army")
