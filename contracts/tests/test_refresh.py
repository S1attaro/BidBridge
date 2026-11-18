import os
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from contracts.management.commands import refresh_jobs
from contracts.models import Contract

from .helpers import write_csv


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def run_refresh(*args):
    out, err = StringIO(), StringIO()
    call_command("refresh_jobs", *args, stdout=out, stderr=err)
    return out.getvalue() + err.getvalue()


@override_settings(SAM_API_KEY="")
class RefreshTests(TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = Path(self.folder) / "data" / "raw" / "ContractOpportunitiesFullCSV.csv"
        patcher = patch.object(refresh_jobs, "extract_path", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        sample = write_csv()
        self.addCleanup(os.remove, sample)
        with open(sample, "rb") as f:
            # Pad the sample so it passes the "too small to be real" check.
            self.body = f.read() + b"\n" * refresh_jobs.MIN_BYTES

    def test_downloads_and_loads_jobs(self):
        with patch.object(refresh_jobs, "urlopen", return_value=FakeResponse(self.body)):
            out = run_refresh()
        self.assertIn("Downloaded", out)
        self.assertTrue(self.path.exists())
        self.assertEqual(Contract.objects.filter(active=True).count(), 3)

    def test_fresh_file_is_not_downloaded_again(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(self.body)
        with patch.object(refresh_jobs, "urlopen") as fake:
            out = run_refresh()
        fake.assert_not_called()
        self.assertIn("Skipping the download", out)
        self.assertEqual(Contract.objects.count(), 3)

    def test_tiny_file_is_rejected_and_old_copy_kept(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(self.body)
        with patch.object(refresh_jobs, "urlopen", return_value=FakeResponse(b"header only\n")):
            out = run_refresh("--force")
        self.assertIn("looks broken", out)
        self.assertIn("older copy", out)
        self.assertEqual(self.path.stat().st_size, len(self.body))
        self.assertEqual(Contract.objects.count(), 3)

    def test_falls_back_to_api_when_no_file(self):
        with patch.object(refresh_jobs, "urlopen", side_effect=OSError("no network")):
            out = run_refresh()
        self.assertIn("Download failed", out)
        self.assertIn("last 30 days from the API", out)
