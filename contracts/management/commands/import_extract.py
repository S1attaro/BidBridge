"""Load the SAM.gov nightly Contract Opportunities CSV.

Download it from https://sam.gov/data-services (Contract Opportunities > datagov >
ContractOpportunitiesFullCSV.csv). It's big, so the file is read one row at a
time and only open notices with a future due date are kept.

    python manage.py import_extract data/raw/ContractOpportunitiesFullCSV.csv
    python manage.py import_extract data.csv --states IL,IN,WI --limit 5000
    python manage.py import_extract data.csv --show-header
"""

import csv
import sys

from django.core.management.base import BaseCommand, CommandError

from contracts import importer

BATCH = 1000


def pick_encoding(path):
    """The file is usually UTF-8, but older extracts were Windows-1252."""
    with open(path, "rb") as f:
        sample = f.read(2_000_000)
    try:
        sample.decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError as e:
        # A cut-off character at the very end of the sample is fine.
        if e.start > len(sample) - 4:
            return "utf-8-sig"
        return "cp1252"


class Command(BaseCommand):
    help = "Import open contracts from the SAM.gov Contract Opportunities CSV."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--states", default="", help="Only keep these states, like IL,IN,WI")
        parser.add_argument("--limit", type=int, default=0, help="Stop after this many contracts")
        parser.add_argument("--all-types", action="store_true", help="Keep award notices and special notices too")
        parser.add_argument("--show-header", action="store_true", help="Print the columns and stop")

    def handle(self, *args, **opts):
        csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
        encoding = pick_encoding(opts["path"])
        states = {s.strip().upper() for s in opts["states"].split(",") if s.strip()}

        try:
            f = open(opts["path"], encoding=encoding, errors="replace", newline="")
        except OSError as e:
            raise CommandError(str(e))

        with f:
            reader = csv.reader(f)
            header = next(reader)
            columns = importer.map_header(header)

            if opts["show_header"]:
                for i, name in enumerate(header):
                    used = [k for k, v in columns.items() if v == i]
                    self.stdout.write(f"{i:3} {name}" + (f"  -> {used[0]}" if used else ""))
                return

            missing = [f for f in ("notice_id", "title", "due") if f not in columns]
            if missing:
                raise CommandError(f"Can't find these columns: {missing}. Run with --show-header to check.")

            agencies = importer.AgencyCache()
            batch, seen, saved = [], 0, 0
            for values in reader:
                seen += 1
                row = importer.row_from_csv(values, columns)
                if not importer.keep_row(row, states, opts["all_types"]):
                    continue
                batch.append(importer.build_contract(row, agencies))
                if len(batch) >= BATCH:
                    saved += importer.save_contracts(batch)
                    batch = []
                    self.stdout.write(f"  {saved} saved ({seen} rows read)")
                if opts["limit"] and saved + len(batch) >= opts["limit"]:
                    break
            saved += importer.save_contracts(batch)

        closed = importer.close_past_due()
        repeats = importer.mark_repeats()
        self.stdout.write(self.style.SUCCESS(
            f"Read {seen} rows ({encoding}). Saved {saved} open contracts. Closed {closed} past due."
        ))
