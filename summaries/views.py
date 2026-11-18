from django.core.cache import cache
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from contracts.models import Contract

from .ai import summarize

HOURLY_LIMIT = 20


def over_limit(request):
    """Simple limit so one visitor can't use up the AI calls."""
    key = f"summary-uses-{request.META.get('REMOTE_ADDR', 'unknown')}"
    uses = cache.get(key, 0)
    if uses >= HOURLY_LIMIT:
        return True
    cache.set(key, uses + 1, 60 * 60)
    return False


@require_POST
def make_summary(request, notice_id):
    """Make a summary if there isn't one yet. Returns the summary box HTML."""
    contract = get_object_or_404(Contract, notice_id=notice_id)
    summary = getattr(contract, "summary", None)
    limited = False
    if summary is None or (summary.source == "simple" and request.POST.get("retry")):
        limited = over_limit(request)
        summary = summarize(contract, use_ai=not limited, allow_fetch=True)
    return render(request, "summaries/summary_box.html", {"contract": contract, "summary": summary, "limited": limited})
