"""Calling outside APIs (SAM.gov and Groq).

Every call is saved in ApiCall (without keys), so we can see failures and
stay under the free limits.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import ApiCall

SAM_SEARCH_URL = "https://api.sam.gov/opportunities/v2/search"
SECRET_PARAMS = {"api_key", "key"}
HEADERS = {"Accept": "application/json", "User-Agent": "BidBridge/1.0"}


class ApiError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def send(source, request, log_url, timeout=30, as_json=True):
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        data = json.loads(body) if as_json else body
    except HTTPError as e:
        ApiCall.objects.create(source=source, endpoint=log_url, ok=False, status=e.code, error=str(e.reason)[:300])
        raise ApiError(f"{source} returned HTTP {e.code} ({e.reason})", status=e.code)
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        ApiCall.objects.create(source=source, endpoint=log_url, ok=False, error=str(e)[:300])
        raise ApiError(f"{source} request failed: {e}")
    ApiCall.objects.create(source=source, endpoint=log_url, ok=True, status=200)
    return data


def get(source, url, params=None, as_json=True):
    params = params or {}
    full_url = f"{url}?{urlencode(params)}" if params else url
    safe = {k: v for k, v in params.items() if k not in SECRET_PARAMS}
    log_url = (f"{url}?{urlencode(safe)}" if safe else url)[:500]
    return send(source, Request(full_url, headers=HEADERS), log_url, as_json=as_json)


def post_json(source, url, body, headers=None, timeout=30):
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={**HEADERS, "Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    return send(source, request, url[:500], timeout)


# ---------- SAM.gov ----------

def sam_calls_today():
    """Every SAM.gov call counts against the daily limit, even failed ones."""
    return ApiCall.objects.filter(source="sam", created_at__date=timezone.localdate()).count()


def sam_calls_left():
    return max(settings.SAM_DAILY_CALL_CAP - sam_calls_today(), 0)


def sam_get(url, params=None, as_json=True):
    if not settings.SAM_API_KEY:
        raise ApiError("SAM_API_KEY is not set in .env")
    if sam_calls_left() <= 0:
        raise ApiError(f"Stopped at the daily cap of {settings.SAM_DAILY_CALL_CAP} SAM.gov calls. Try again tomorrow.")
    params = {**(params or {}), "api_key": settings.SAM_API_KEY}
    return get("sam", url, params, as_json=as_json)


def search_notices(posted_from, posted_to, offset=0, limit=1000):
    """One page of notices posted between two dates (date objects)."""
    params = {
        "postedFrom": posted_from.strftime("%m/%d/%Y"),
        "postedTo": posted_to.strftime("%m/%d/%Y"),
        "limit": limit,
        "offset": offset,
    }
    return sam_get(SAM_SEARCH_URL, params)


def fetch_description(url):
    """The full text of one notice. The API gives a link that needs our key."""
    data = sam_get(url, as_json=False)
    try:
        parsed = json.loads(data)
        return parsed.get("description") or ""
    except (json.JSONDecodeError, AttributeError):
        return data
