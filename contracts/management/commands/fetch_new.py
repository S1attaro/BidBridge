"""Get notices posted in the last few days from the SAM.gov API.

The free key allows about 10 calls a day, so this stops at SAM_DAILY_CALL_CAP.
Each call returns up to 1,000 notices.

    python manage.py fetch_new            # last 2 days
    python manage.py fetch_new --days 5 --states IL,IN
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts import clients, importer


class Command(BaseCommand):
    help = "Fetch newly posted notices from the SAM.gov API (respects the daily call cap)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=2)
        parser.add_argument("--states", default="")
        parser.add_argument("--max-calls", type=int, default=3)

    def handle(self, *args, **opts):
        today = timezone.localdate()
        start = today - timedelta(days=opts["days"])
        states = {s.strip().upper() for s in opts["states"].split(",") if s.strip()}
        agencies = importer.AgencyCache()

        offset, saved, calls = 0, 0, 0
        while calls < opts["max_calls"]:
            try:
                data = clients.search_notices(start, today, offset=offset)
            except clients.ApiError as e:
                self.stderr.write(str(e))
                break
            calls += 1
            items = data.get("opportunitiesData") or []
            rows = [importer.row_from_api(item) for item in items]
            batch = [importer.build_contract(r, agencies) for r in rows if importer.keep_row(r, states)]
            saved += importer.save_contracts(batch, keep_text=True)
            offset += len(items)
            if not items or offset >= int(data.get("totalRecords") or 0):
                break

        importer.mark_repeats()
        self.stdout.write(self.style.SUCCESS(
            f"Saved {saved} open contracts using {calls} calls. {clients.sam_calls_left()} calls left today."
        ))
