"""Make plain summaries ahead of time so pages open fast.

    python manage.py summarize --limit 50 --state IL
    python manage.py summarize --limit 20 --trade roofing --fetch-text
    python manage.py summarize --redo --limit 10     # remake old ones
    python manage.py summarize --fix-simple --state IL   # try the AI again on simple ones
"""

import time

from django.core.management.base import BaseCommand

from contracts.filters import filter_contracts
from summaries.ai import summarize

RETRY_WAIT = 30  # seconds to wait when Groq says it's busy


class Command(BaseCommand):
    help = "Make plain summaries for open contracts."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--state", default="")
        parser.add_argument("--trade", default="")
        parser.add_argument("--fetch-text", action="store_true", help="Fetch missing posting text from SAM.gov")
        parser.add_argument("--simple", action="store_true", help="No AI, just the simple summary")
        parser.add_argument("--redo", action="store_true", help="Remake summaries that already exist")
        parser.add_argument("--fix-simple", action="store_true", help="Try the AI again on simple summaries")
        parser.add_argument("--wait", type=float, default=3, help="Seconds between AI calls")

    def handle(self, *args, **opts):
        qs = filter_contracts({"state": opts["state"], "trade": opts["trade"]})
        if opts["fix_simple"]:
            qs = qs.filter(summary__source="simple")
        elif not opts["redo"]:
            qs = qs.filter(summary__isnull=True)
        use_ai = not opts["simple"]
        counts = {"ai": 0, "simple": 0}

        for contract in list(qs[:opts["limit"]]):
            summary = summarize(contract, use_ai=use_ai, allow_fetch=opts["fetch_text"])
            if use_ai and summary.source == "simple":
                self.stdout.write(f"  Groq is busy. Waiting {RETRY_WAIT} seconds, then trying again.")
                time.sleep(RETRY_WAIT)
                summary = summarize(contract, use_ai=use_ai, allow_fetch=opts["fetch_text"])
            counts[summary.source] += 1
            self.stdout.write(f"  {summary.source:6} {contract.notice_id} {contract.title[:60]}")
            if use_ai:
                time.sleep(opts["wait"])

        self.stdout.write(self.style.SUCCESS(f"Done: {counts['ai']} AI summaries, {counts['simple']} simple."))
