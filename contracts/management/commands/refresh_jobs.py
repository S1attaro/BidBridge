"""Keep the job list up to date with no manual steps.

1. Download SAM.gov's free nightly file of every notice (no key needed, no call limit).
   Skipped if the copy on disk is less than 20 hours old.
2. Load the open jobs from it and close jobs that are past due.
3. Use the API to add anything posted since the file was made.
4. Email new jobs to users who turned on job alerts.

If the download fails, it falls back to the API and loads the last 30 days.

    python manage.py refresh_jobs
    python manage.py refresh_jobs --force      # download again even if the file is new
    python manage.py refresh_jobs --no-download
"""

import os
import shutil
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from contracts import clients, importer

EXTRACT_URL = (
    "https://sam.gov/api/prod/fileextractservices/v1/api/download/"
    "Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv?privacy=Public"
)
MAX_AGE_HOURS = 20
# A real file is hundreds of MB. Anything tiny is a broken or header-only file.
MIN_BYTES = 1_000_000


def extract_path():
    return Path(settings.BASE_DIR) / "data" / "raw" / "ContractOpportunitiesFullCSV.csv"


def file_is_fresh(path, hours=MAX_AGE_HOURS):
    return path.exists() and time.time() - path.stat().st_mtime < hours * 3600


def download(url, path, log=print):
    """Save the file to a temp name first, so a failed download keeps the old copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".part")
    request = Request(url, headers={"User-Agent": "BidBridge/1.0"})
    with urlopen(request, timeout=120) as response, open(temp, "wb") as f:
        shutil.copyfileobj(response, f, length=1024 * 1024)
    size = temp.stat().st_size
    if size < MIN_BYTES:
        temp.unlink()
        raise ValueError(f"The file was only {size:,} bytes, so it looks broken.")
    os.replace(temp, path)
    log(f"Downloaded {size / 1_000_000:.0f} MB.")


class Command(BaseCommand):
    help = "Download the SAM.gov nightly file, load open jobs, then add new ones from the API."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Download even if the file is new")
        parser.add_argument("--no-download", action="store_true", help="Only use the API")
        parser.add_argument("--url", default=os.getenv("SAM_EXTRACT_URL", EXTRACT_URL))

    def handle(self, *args, **opts):
        path = extract_path()
        have_file = False

        if not opts["no_download"]:
            if file_is_fresh(path) and not opts["force"]:
                self.stdout.write("The SAM.gov file is from today. Skipping the download.")
                have_file = True
            else:
                self.stdout.write("Downloading the SAM.gov file. This can take a few minutes.")
                try:
                    download(opts["url"], path, self.stdout.write)
                    have_file = True
                except (URLError, OSError, ValueError) as e:
                    self.stderr.write(f"Download failed: {e}")
                    have_file = path.exists()
                    if have_file:
                        self.stdout.write("Using the older copy on disk.")

        if have_file:
            call_command("import_extract", str(path), stdout=self.stdout, stderr=self.stderr)
            days = 2
        else:
            self.stdout.write("No SAM.gov file, so loading the last 30 days from the API.")
            days = 30

        closed = importer.close_past_due()
        if closed:
            self.stdout.write(f"Closed {closed} jobs that are past due.")

        # Keep 2 calls for reading full postings when making AI summaries.
        calls = clients.sam_calls_left() - 2
        if calls > 0:
            call_command("fetch_new", days=days, max_calls=calls, stdout=self.stdout, stderr=self.stderr)
        else:
            self.stdout.write("No API calls left today. New jobs will come in tomorrow.")

        call_command("send_alerts", stdout=self.stdout, stderr=self.stderr)
        self.stdout.write(self.style.SUCCESS("Done."))
