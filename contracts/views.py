from datetime import timezone as dt_timezone

from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from . import codes, geo
from .filters import WHEN, WHEN_KEYS, ContractFilterForm, filter_contracts, open_contracts, when_q
from .models import BidClick, Contract

# The due-date buttons above the list. The bands themselves are in filters.WHEN.
DUE_CHOICES = [("", "All", None)] + [(key, label, color) for key, label, _, _, color in WHEN]
# On the overview, each band shows only a few jobs so one band can't fill the page.
PREVIEW = 5
NOTES = {"today": "Under a day left. Most bids take longer than that to put together."}


def user_profile(user):
    if not user.is_authenticated:
        return None
    from matches.models import ContractorProfile
    return ContractorProfile.objects.filter(user=user).first()


def add_personal_facts(contracts, profile):
    """Add distance from the user's business and whether they can bid, for display."""
    home = geo.locate(profile.zip_code) if profile and profile.zip_code else None
    for c in contracts:
        c.miles = geo.miles_between(home, (c.lat, c.lon)) if home and c.lat is not None else None
        c.can_bid = profile.can_bid(c.set_aside) if profile else None
    return contracts


def active_filters(form, params):
    """The filters in use, each with a link that removes it. (Used by older links and tests.)"""
    found = []
    for name in ["q", "trade", "state", "set_aside", "due_within"]:
        value = params.get(name)
        if not value:
            continue
        field = form.fields[name]
        label = dict(field.choices).get(value, value) if hasattr(field, "choices") else f'"{value}"'
        rest = params.copy()
        rest.pop(name, None)
        rest.pop("page", None)
        found.append({"label": label, "remove": "?" + rest.urlencode()})
    return found


class ContractListView(ListView):
    """The main page: map and state list on top, jobs below. Also returns just the jobs for live updates."""

    template_name = "contracts/browse.html"
    context_object_name = "contracts"
    paginate_by = 40

    def get(self, request, *args, **kwargs):
        params = request.GET.copy()
        params.pop("page", None)
        request.session["last_browse"] = params.urlencode()
        self.profile = user_profile(request.user)
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.headers.get("X-Partial"):
            return ["contracts/results.html"]
        return [self.template_name]

    def get_queryset(self):
        return filter_contracts(self.request.GET, profile=self.profile).select_related("summary")

    def get_paginate_by(self, queryset):
        # Pages only when one band is picked. The overview shows a few jobs from each band.
        return self.paginate_by if self.when() else None

    def when(self):
        value = self.request.GET.get("when")
        return value if value in WHEN_KEYS else ""

    def overview(self, queryset):
        groups = []
        for key, label, _, _, color in WHEN:
            band = queryset.filter(when_q(key))
            count = band.count()
            if count:
                items = add_personal_facts(list(band[:PREVIEW]), self.profile)
                groups.append({"key": key, "label": label, "days": color, "items": items,
                               "count": count, "note": NOTES.get(key, "")})
        return groups

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        when = self.when()
        if when:
            page = add_personal_facts(list(context["contracts"]), self.profile)
            _, label, _, _, color = WHEN[WHEN_KEYS.index(when)]
            count = context["paginator"].count
            context["groups"] = [{"key": when, "label": label, "days": color, "items": page,
                                  "count": count, "note": NOTES.get(when, "")}] if page else []
            context["total"] = count
        else:
            context["groups"] = self.overview(context["object_list"])
            context["total"] = sum(g["count"] for g in context["groups"])
        context["when"] = when
        context["query_string"] = params.urlencode()
        context["profile"] = self.profile
        if self.request.headers.get("X-Partial"):
            return context

        counts = dict(open_contracts().exclude(place_state="").values_list("place_state").annotate(n=Count("id")).values_list("place_state", "n"))
        context["state_counts"] = counts
        context["states"] = [{"code": c, "name": n, "count": counts.get(c, 0)} for c, n in codes.STATE_CHOICES]
        context["picked"] = [s.upper() for s in self.request.GET.getlist("state") if s.upper() in codes.STATES]
        context["trades"] = codes.TRADE_CHOICES
        context["due_choices"] = DUE_CHOICES
        # Count every open job, including ones with no state listed (they aren't on the map).
        context["total_open"] = open_contracts().count()
        context["form"] = ContractFilterForm(self.request.GET or None)
        context["active_filters"] = active_filters(context["form"], self.request.GET)
        return context


class ContractDetailView(DetailView):
    template_name = "contracts/contract_detail.html"
    context_object_name = "contract"
    slug_field = "notice_id"
    slug_url_kwarg = "notice_id"

    def get_queryset(self):
        return Contract.objects.select_related("agency", "summary")

    def get_template_names(self):
        if self.request.GET.get("panel"):
            return ["contracts/panel.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile = user_profile(user)
        add_personal_facts([self.object], profile)
        context["miles"] = self.object.miles
        context["can_bid"] = self.object.can_bid
        context["is_saved"] = user.is_authenticated and self.object.saves.filter(user=user).exists()
        return context


@require_POST
def bid_click(request, notice_id):
    """Count a click on "Bid on SAM.gov". Sent in the background, so it never slows the user down."""
    contract = get_object_or_404(Contract, notice_id=notice_id)
    page = (request.POST.get("page") or "")[:30]
    BidClick.objects.create(contract=contract, user=request.user if request.user.is_authenticated else None, page=page)
    return HttpResponse(status=204)


def calendar_file(request, notice_id):
    """A calendar event for the due date, so it shows up in Outlook or Google Calendar."""
    contract = get_object_or_404(Contract, notice_id=notice_id)
    if not contract.due_date:
        raise Http404
    due = contract.due_date.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    title = f"Bid due: {contract.title}".replace(",", "\\,").replace(";", "\\;")[:150]
    link = request.build_absolute_uri(contract.get_absolute_url())
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BidBridge//EN", "BEGIN:VEVENT",
        f"UID:{contract.notice_id}@bidbridge", f"DTSTAMP:{due}", f"DTSTART:{due}", f"DTEND:{due}",
        f"SUMMARY:{title}", f"DESCRIPTION:{link}", f"URL:{link}",
        "BEGIN:VALARM", "TRIGGER:-P2D", "ACTION:DISPLAY", "DESCRIPTION:Bid due in 2 days", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    response = HttpResponse("\r\n".join(lines), content_type="text/calendar")
    response["Content-Disposition"] = f'attachment; filename="bid-due-{contract.notice_id[:20]}.ics"'
    return response
