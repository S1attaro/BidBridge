"""Search, filter, and sort contracts. Used by the browse page and the JSON API."""

from datetime import datetime, time, timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from . import codes
from .models import Contract

SORTS = {
    "due": ("Due soonest", ["due_date"]),
    "new": ("Newest", ["-posted_date"]),
    "days": ("Most time left", ["-due_date"]),
}

DUE_CHOICES = [("", "Any time"), ("7", "Next 7 days"), ("14", "Next 2 weeks"), ("30", "Next 30 days")]


class ContractFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    trade = forms.ChoiceField(required=False, label="Work", choices=[("", "Any work")] + codes.TRADE_CHOICES)
    state = forms.ChoiceField(required=False, label="State", choices=[("", "Any state")] + codes.STATE_CHOICES)
    set_aside = forms.ChoiceField(
        required=False, label="Who can bid", choices=[("", "Anyone")] + codes.SET_ASIDE_CHOICES
    )
    due_within = forms.ChoiceField(required=False, label="Due", choices=DUE_CHOICES)
    sort = forms.ChoiceField(
        required=False, label="Sort by", choices=[(k, v[0]) for k, v in SORTS.items()]
    )


# Due-date bands: (key, label, first day, last day, day used for the color).
# Days count from today in local time, so "Closes today" means before midnight tonight.
WHEN = [
    ("today", "Closes today", 0, 0, 0),
    ("week", "This week", 1, 7, 4),
    ("next", "Next week", 8, 14, 11),
    ("later", "Later", 15, None, 21),
]
WHEN_KEYS = [w[0] for w in WHEN]


def midnight(days_from_today):
    day = timezone.localdate() + timedelta(days=days_from_today)
    return timezone.make_aware(datetime.combine(day, time.min))


def when_q(key):
    """Database filter for one due-date band."""
    for k, _, first, last, _ in WHEN:
        if k == key:
            q = Q(due_date__gte=midnight(first)) if first else Q()
            if last is not None:
                q &= Q(due_date__lt=midnight(last + 1))
            return q
    return Q()


def open_contracts():
    """Jobs you can still bid on. Parts orders and reposted copies are left out."""
    return Contract.objects.filter(
        active=True, due_date__gt=timezone.now(), is_goods=False, is_repeat=False,
    ).select_related("agency")


def many(params, name):
    """All values for a name, from request.GET (several) or a plain dict (one)."""
    if hasattr(params, "getlist"):
        return [v for v in params.getlist(name) if v]
    value = params.get(name)
    return value if isinstance(value, list) else ([value] if value else [])


def can_bid_q(profile):
    """Contracts this profile is allowed to bid on, by set-aside."""
    allowed = Q(set_aside="") | Q(set_aside__iexact="NONE")
    for group, (name, group_codes) in codes.SET_ASIDE_GROUPS.items():
        if group != "none" and profile.can_bid(group_codes[0]):
            allowed |= Q(set_aside__in=group_codes)
    return allowed


def filter_contracts(params, queryset=None, profile=None):
    """Apply the filters in params (a dict like request.GET). Bad values are ignored."""
    qs = open_contracts() if queryset is None else queryset

    words = (params.get("q") or "").strip()
    for word in words.split()[:6]:
        qs = qs.filter(
            Q(title__icontains=word) | Q(description_text__icontains=word)
            | Q(agency__sub_tier__icontains=word) | Q(place_city__icontains=word)
            | Q(solicitation_number__iexact=word)
        )

    trade = params.get("trade")
    if trade in codes.TRADES:
        trade_q = Q()
        for code in codes.naics_codes(trade):
            trade_q |= Q(naics_code__startswith=code)
        qs = qs.filter(trade_q)

    states = [s.upper() for s in many(params, "state") if s.upper() in codes.STATES]
    if states:
        qs = qs.filter(place_state__in=states)

    if params.get("can_bid") and profile is not None:
        qs = qs.filter(can_bid_q(profile))

    group = params.get("set_aside")
    if group == "none":
        qs = qs.filter(Q(set_aside="") | Q(set_aside__iexact="NONE"))
    elif group in codes.SET_ASIDE_GROUPS:
        qs = qs.filter(set_aside__in=codes.SET_ASIDE_GROUPS[group][1])

    due = params.get("due_within")
    if due and str(due).isdigit():
        qs = qs.filter(due_date__lte=timezone.now() + timedelta(days=int(due)))

    when = params.get("when")
    if when in WHEN_KEYS:
        qs = qs.filter(when_q(when))

    sort = params.get("sort")
    order = SORTS.get(sort, SORTS["due"])[1]
    return qs.order_by(*order, "id")
