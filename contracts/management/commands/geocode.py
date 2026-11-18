"""Fill in map points for contracts that don't have one yet (uses data/zips.csv).

    python manage.py geocode
"""

from django.core.management.base import BaseCommand

from contracts import geo
from contracts.models import Contract


class Command(BaseCommand):
    help = "Add map points (lat/lon) to contracts from their ZIP code or city."

    def handle(self, *args, **opts):
        found = missing = 0
        for c in Contract.objects.filter(lat__isnull=True).iterator():
            point = geo.locate(c.place_zip, c.place_city, c.place_state)
            if point:
                Contract.objects.filter(pk=c.pk).update(lat=point[0], lon=point[1])
                found += 1
            else:
                missing += 1
        self.stdout.write(self.style.SUCCESS(f"Added map points to {found} contracts. {missing} had no usable place."))
