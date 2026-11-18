"""Turn SAM.gov rows (from the nightly CSV or the API) into Contract records."""

import re
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from . import codes, geo
from .models import Agency, Contract

# CSV header -> our field. Headers are matched after lowercasing and dropping
# anything that isn't a letter or number, so "Sol#" becomes "sol".
CSV_COLUMNS = {
    "notice_id": ["noticeid"],
    "title": ["title"],
    "solicitation_number": ["sol", "solicitationnumber"],
    "department": ["departmentindagency", "department"],
    "sub_tier": ["subtier"],
    "office": ["office"],
    "posted": ["posteddate"],
    "notice_type": ["type", "noticetype"],
    "set_aside": ["setasidecode", "typeofsetaside"],
    "due": ["responsedeadline"],
    "naics_code": ["naicscode"],
    "psc_code": ["classificationcode"],
    "city": ["popcity"],
    "state": ["popstate"],
    "zip": ["popzip"],
    "active": ["active"],
    "award": ["award"],
    "link": ["link", "uilink"],
    "description": ["description"],
}

UPDATE_FIELDS = [
    "title", "solicitation_number", "agency", "notice_type", "naics_code", "psc_code", "set_aside",
    "posted_date", "due_date", "place_city", "place_state", "place_zip", "lat", "lon", "award_amount", "sam_url",
    "description_text", "description_url", "active", "short_title", "is_goods", "dupe_key",
]


def clean_header(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def map_header(header):
    """Return {our field: column index} for the columns we know."""
    cleaned = [clean_header(h) for h in header]
    found = {}
    for field, names in CSV_COLUMNS.items():
        for name in names:
            if name in cleaned:
                found[field] = cleaned.index(name)
                break
    return found


def parse_date(value):
    """SAM.gov dates come in a few shapes. Return an aware datetime or None."""
    value = (value or "").strip()
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    # "2026-11-10 13:44:33.693-05" -> ISO with a full offset
    text = re.sub(r"([+-]\d{2})$", r"\1:00", text)
    try:
        result = datetime.fromisoformat(text)
    except ValueError:
        result = None
        for fmt in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                result = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if result is None:
            match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
            if not match:
                return None
            result = datetime.fromisoformat(match.group(1))
    if result.tzinfo is None:
        if result.time() == time(0, 0):
            # A date with no time: count it as due at the end of that day.
            result = result.replace(hour=23, minute=59)
        result = timezone.make_aware(result)
    return result


def parse_money(value):
    value = re.sub(r"[^0-9.]", "", str(value or ""))
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def is_link(text):
    return bool(re.match(r"^https?://\S+$", (text or "").strip()))


def row_from_csv(values, columns):
    """Pull our fields out of one CSV row."""
    def get(field):
        i = columns.get(field)
        if i is None or i >= len(values):
            return ""
        return (values[i] or "").strip()

    return {field: get(field) for field in CSV_COLUMNS}


def row_from_api(item):
    """Pull our fields out of one record from the SAM.gov search API."""
    path = (item.get("fullParentPathName") or "").split(".")
    place = item.get("placeOfPerformance") or {}
    award = item.get("award") or {}
    return {
        "notice_id": item.get("noticeId") or "",
        "title": item.get("title") or "",
        "solicitation_number": item.get("solicitationNumber") or "",
        "department": path[0] if len(path) > 0 else "",
        "sub_tier": path[1] if len(path) > 1 else "",
        "office": path[-1] if len(path) > 2 else "",
        "posted": item.get("postedDate") or "",
        "notice_type": item.get("type") or "",
        "set_aside": item.get("typeOfSetAside") or "",
        "due": item.get("responseDeadLine") or "",
        "naics_code": item.get("naicsCode") or "",
        "psc_code": item.get("classificationCode") or "",
        "city": ((place.get("city") or {}).get("name")) or "",
        "state": ((place.get("state") or {}).get("code")) or "",
        "zip": place.get("zip") or "",
        "active": item.get("active") or "",
        "award": award.get("amount") or "",
        "link": item.get("uiLink") or "",
        "description": item.get("description") or "",
    }


def keep_row(row, states=None, all_types=False):
    """True if the row is an open notice someone could still respond to."""
    if not row["notice_id"] or not row["title"]:
        return False
    if row["active"] and row["active"].lower() not in ("yes", "true", "y", "1"):
        return False
    if not all_types and row["notice_type"] not in codes.NOTICE_TYPES:
        return False
    if states and row["state"].upper()[:2] not in states:
        return False
    due = parse_date(row["due"])
    return due is not None and due > timezone.now()


class AgencyCache:
    """Look up or create agencies without hitting the database for every row."""

    def __init__(self):
        self.known = {}

    def get(self, row):
        key = (row["department"][:200], row["sub_tier"][:200], row["office"][:200])
        if not key[0]:
            return None
        if key not in self.known:
            self.known[key], _ = Agency.objects.get_or_create(name=key[0], sub_tier=key[1], office=key[2])
        return self.known[key]


def build_contract(row, agencies):
    description = row["description"]
    link = f"https://sam.gov/opp/{row['notice_id']}/view"
    point = geo.locate(row["zip"], row["city"], row["state"])
    return Contract(
        notice_id=row["notice_id"][:64],
        title=row["title"][:500],
        solicitation_number=row["solicitation_number"][:128],
        agency=agencies.get(row),
        notice_type=row["notice_type"][:80],
        naics_code=row["naics_code"][:10],
        psc_code=row["psc_code"][:10],
        set_aside=row["set_aside"][:20],
        posted_date=parse_date(row["posted"]),
        due_date=parse_date(row["due"]),
        place_city=row["city"][:100],
        place_state=row["state"].upper()[:2],
        place_zip=row["zip"][:5],
        lat=point[0] if point else None,
        lon=point[1] if point else None,
        award_amount=parse_money(row["award"]),
        sam_url=link[:300],
        description_url=description[:300] if is_link(description) else "",
        description_text="" if is_link(description) else description,
        active=True,
    ).tidy()


def save_contracts(contracts, keep_text=False):
    """Insert new contracts and update ones we already have. Returns how many were saved.

    keep_text=True leaves any saved description alone (the API only gives a link to it).
    """
    unique = {c.notice_id: c for c in contracts}
    if not unique:
        return 0
    fields = [f for f in UPDATE_FIELDS if not (keep_text and f == "description_text")]
    Contract.objects.bulk_create(
        list(unique.values()),
        update_conflicts=True,
        unique_fields=["notice_id"],
        update_fields=fields,
    )
    return len(unique)


def mark_repeats(model=Contract):
    """Show one copy of each job: the newest posting. Run after every import.

    `model` lets the data migration pass in its own copy of Contract.
    """
    now = timezone.now()
    open_jobs = model.objects.filter(active=True, due_date__gt=now).exclude(dupe_key="")
    model.objects.filter(is_repeat=True).update(is_repeat=False)
    seen, repeats = set(), []
    rows = open_jobs.order_by("dupe_key", "-posted_date", "-id").values_list("id", "dupe_key")
    for pk, key in rows.iterator():
        if key in seen:
            repeats.append(pk)
        seen.add(key)
    for i in range(0, len(repeats), 500):
        model.objects.filter(id__in=repeats[i:i + 500]).update(is_repeat=True)
    label_look_alikes(model)
    return len(repeats)


def label_look_alikes(model=Contract):
    """Different jobs can get the same short title (like five dredging contracts on one river).
    Add the contract or solicitation number so they don't look like repeats."""
    from django.db.models import Count

    from .cleanup import short_title, tell_apart

    shown = model.objects.filter(active=True, due_date__gt=timezone.now(), is_goods=False, is_repeat=False)
    shared = shown.values("short_title").annotate(n=Count("id")).filter(n__gt=1).values_list("short_title", flat=True)
    changed = []
    for name in list(shared):
        jobs = list(shown.filter(short_title=name))
        # First try the longer title. It often has the part that differs, like "Coordinating Center".
        longer = [short_title(j.title, max_len=115) for j in jobs]
        if len(set(longer)) == len(longer):
            for job, title in zip(jobs, longer):
                job.short_title = title
                changed.append(job)
            continue
        tags = [tell_apart(j.title, j.solicitation_number) for j in jobs]
        # Where two jobs still get the same tag, use the solicitation number (always different).
        clash = {t for t in tags if tags.count(t) > 1}
        tags = [j.solicitation_number or j.notice_id[:8] if t in clash else t for j, t in zip(jobs, tags)]
        for job, tag in zip(jobs, tags):
            job.short_title = f"{name[:100].rstrip('…')} {tag}".strip()[:120]
            changed.append(job)
    model.objects.bulk_update(changed, ["short_title"], batch_size=500)

    # Last check: anything still shared gets its solicitation number, which is always different.
    still = shown.values("short_title").annotate(n=Count("id")).filter(n__gt=1).values_list("short_title", flat=True)
    last = []
    for name in list(still):
        for job in shown.filter(short_title=name):
            tag = job.solicitation_number or job.notice_id[:8]
            if not job.short_title.endswith(tag):
                job.short_title = f"{name[:100].rstrip('…')} {tag}".strip()[:120]
                last.append(job)
    model.objects.bulk_update(last, ["short_title"], batch_size=500)
    return len(changed) + len(last)


def close_past_due():
    """Mark contracts whose due date has passed as not active."""
    return Contract.objects.filter(active=True, due_date__lt=timezone.now()).update(active=False)
