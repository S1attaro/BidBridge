"""ZIP codes to map points, and miles between two places.

data/zips.csv comes from the free "zipcodes" package (U.S. ZIP centers).
It's loaded once, the first time it's needed.
"""

import csv
import math
from functools import lru_cache

from django.conf import settings

ZIP_FILE = settings.BASE_DIR / "data" / "zips.csv"


@lru_cache(maxsize=1)
def _tables():
    by_zip, by_city = {}, {}
    try:
        with open(ZIP_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                point = (float(row["lat"]), float(row["lon"]))
                by_zip[row["zip"]] = point
                by_city.setdefault((row["city"].upper(), row["state"]), point)
    except FileNotFoundError:
        pass
    return by_zip, by_city


def locate(zip_code="", city="", state=""):
    """(lat, lon) for a ZIP code, or for a city and state. None if unknown."""
    by_zip, by_city = _tables()
    zip_code = (zip_code or "").strip()[:5]
    if zip_code in by_zip:
        return by_zip[zip_code]
    return by_city.get(((city or "").strip().upper(), (state or "").strip().upper()))


def miles_between(a, b):
    """Straight-line miles between two (lat, lon) points."""
    if not a or not b:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return round(3958.8 * 2 * math.asin(math.sqrt(h)))
