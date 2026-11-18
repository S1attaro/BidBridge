import os
from datetime import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from contracts import importer
from contracts.models import Agency, Contract

from .helpers import HEADER, sample_rows, write_csv


def run_import(path, *args):
    out = StringIO()
    call_command("import_extract", path, *args, stdout=out)
    return out.getvalue()


class ParseTests(TestCase):
    def test_header_names_are_matched_loosely(self):
        columns = importer.map_header(["Notice Id", "TITLE", "Sol#", "ResponseDeadLine"])
        self.assertEqual(columns, {"notice_id": 0, "title": 1, "solicitation_number": 2, "due": 3})

    def test_parse_iso_date_with_offset(self):
        d = importer.parse_date("2026-12-01T17:00:00-05:00")
        self.assertEqual((d.year, d.month, d.day), (2026, 12, 1))
        self.assertIsNotNone(d.tzinfo)

    def test_parse_short_offset(self):
        d = importer.parse_date("2026-11-10 13:44:33.693-05")
        self.assertEqual(d.utcoffset().total_seconds(), -5 * 3600)

    def test_parse_us_date_counts_as_end_of_day(self):
        d = timezone.localtime(importer.parse_date("12/01/2026"))
        self.assertEqual((d.month, d.day, d.hour), (12, 1, 23))

    def test_bad_date_is_none(self):
        self.assertIsNone(importer.parse_date("soon"))
        self.assertIsNone(importer.parse_date(""))

    def test_money(self):
        self.assertEqual(str(importer.parse_money("$1,250.50")), "1250.50")
        self.assertIsNone(importer.parse_money(""))

    def test_api_row(self):
        item = {
            "noticeId": "abc", "title": "Mow lawns", "fullParentPathName": "AGRICULTURE.FOREST SERVICE.R9",
            "type": "Solicitation", "typeOfSetAside": "SBA", "responseDeadLine": "2026-12-01T17:00:00-05:00",
            "naicsCode": "561730", "active": "Yes",
            "placeOfPerformance": {"city": {"name": "Marion"}, "state": {"code": "IL"}, "zip": "62959"},
            "description": "https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=abc",
        }
        row = importer.row_from_api(item)
        self.assertEqual(row["sub_tier"], "FOREST SERVICE")
        self.assertEqual(row["office"], "R9")
        self.assertEqual(row["state"], "IL")
        self.assertEqual(row["set_aside"], "SBA")


class ImportCommandTests(TestCase):
    def tearDown(self):
        for path in getattr(self, "paths", []):
            os.remove(path)

    def csv_file(self, **kwargs):
        path = write_csv(**kwargs)
        self.paths = getattr(self, "paths", []) + [path]
        return path

    def test_keeps_only_open_biddable_notices(self):
        run_import(self.csv_file())
        self.assertEqual(sorted(Contract.objects.values_list("notice_id", flat=True)), ["n1", "n2", "n6"])

    def test_fields_are_saved(self):
        run_import(self.csv_file())
        c = Contract.objects.get(notice_id="n1")
        self.assertEqual(c.place_state, "IL")
        self.assertEqual(c.naics_code, "238160")
        self.assertEqual(c.set_aside, "SBA")
        self.assertEqual(c.agency.sub_tier, "DEPT OF THE ARMY")
        self.assertEqual(c.sam_url, "https://sam.gov/opp/n1/view")
        self.assertEqual(c.description_text, "Replace the roof on building 5.")

    def test_map_point_added_on_import(self):
        run_import(self.csv_file())
        c = Contract.objects.get(notice_id="n1")
        self.assertAlmostEqual(c.lat, 40.7, places=0)
        self.assertAlmostEqual(c.lon, -89.6, places=0)

    def test_geocode_command_fills_old_rows(self):
        run_import(self.csv_file())
        Contract.objects.update(lat=None, lon=None)
        call_command("geocode", stdout=StringIO())
        self.assertFalse(Contract.objects.filter(lat__isnull=True).exists())

    def test_description_link_is_kept_apart(self):
        run_import(self.csv_file())
        c = Contract.objects.get(notice_id="n2")
        self.assertEqual(c.description_text, "")
        self.assertIn("noticedesc", c.description_url)
        self.assertEqual(c.sam_url, "https://sam.gov/opp/n2/view")

    def test_state_filter(self):
        run_import(self.csv_file(), "--states", "TX")
        self.assertEqual(list(Contract.objects.values_list("notice_id", flat=True)), ["n6"])

    def test_running_twice_updates_instead_of_duplicating(self):
        path = self.csv_file()
        run_import(path)
        rows = sample_rows()
        rows[0][1] = "Roof repair Building 5 (changed)"
        run_import(self.csv_file(rows=rows))
        self.assertEqual(Contract.objects.filter(notice_id="n1").count(), 1)
        self.assertEqual(Contract.objects.get(notice_id="n1").title, "Roof repair Building 5 (changed)")
        self.assertEqual(Agency.objects.filter(sub_tier="DEPT OF THE ARMY").count(), 1)

    def test_limit(self):
        run_import(self.csv_file(), "--limit", "1")
        self.assertEqual(Contract.objects.count(), 1)

    def test_windows_encoding_is_read(self):
        rows = sample_rows()
        rows[0][1] = "Café roof – phase 2"
        run_import(self.csv_file(rows=rows, encoding="cp1252"))
        self.assertEqual(Contract.objects.get(notice_id="n1").title, "Café roof – phase 2")

    def test_missing_columns_gives_clear_error(self):
        path = self.csv_file(header=["Foo", "Bar"], rows=[["1", "2"]])
        with self.assertRaises(CommandError):
            run_import(path)

    def test_show_header(self):
        out = run_import(self.csv_file(), "--show-header")
        self.assertIn("ResponseDeadLine  -> due", out)
        self.assertEqual(Contract.objects.count(), 0)
