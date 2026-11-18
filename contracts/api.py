"""Small read-only JSON API.

GET /api/contracts/?q=roof&state=IL&trade=roofing&set_aside=small&due_within=30&sort=due&limit=20
GET /api/contracts/<notice_id>/
"""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .filters import filter_contracts
from .models import Contract

MAX_LIMIT = 100


def contract_json(c, full=False):
    data = {
        "notice_id": c.notice_id,
        "title": c.title,
        "agency": c.agency.short_name if c.agency else "",
        "trade": c.trade_name,
        "naics_code": c.naics_code,
        "set_aside": c.set_aside_name,
        "notice_type": c.notice_type_name,
        "place": c.place,
        "state": c.place_state,
        "due_date": c.due_date.isoformat() if c.due_date else None,
        "days_left": c.days_left,
        "sam_url": c.bid_url,
        "is_demo": c.is_demo,
    }
    if full:
        data["solicitation_number"] = c.solicitation_number
        data["posted_date"] = c.posted_date.isoformat() if c.posted_date else None
        data["description"] = c.description_text
    return data


def contract_list(request):
    try:
        limit = min(max(int(request.GET.get("limit", 20)), 1), MAX_LIMIT)
        offset = max(int(request.GET.get("offset", 0)), 0)
    except ValueError:
        return JsonResponse({"error": "limit and offset must be whole numbers"}, status=400)
    qs = filter_contracts(request.GET)
    total = qs.count()
    results = [contract_json(c) for c in qs[offset:offset + limit]]
    return JsonResponse({"count": total, "limit": limit, "offset": offset, "results": results})


def contract_detail(request, notice_id):
    contract = get_object_or_404(Contract, notice_id=notice_id)
    return JsonResponse(contract_json(contract, full=True))
