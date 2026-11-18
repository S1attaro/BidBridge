from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from contracts.views import add_personal_facts

from .forms import ProfileForm
from .matching import refresh_matches
from .models import ContractorProfile

MATCHES_GOOD_FOR = timedelta(hours=12)


def get_profile(user):
    return ContractorProfile.objects.filter(user=user).first()


def matches_are_old(profile):
    newest = profile.matches.order_by("-created_at").first()
    if newest is None:
        return True
    return newest.created_at < profile.updated_at or newest.created_at < timezone.now() - MATCHES_GOOD_FOR


def top_matches(profile, count):
    if matches_are_old(profile):
        refresh_matches(profile)
    return profile.matches.select_related("contract", "contract__agency")[:count]


@login_required
def edit_profile(request):
    profile = get_profile(request.user)
    initial = {} if profile else {"alert_email": request.user.email}
    form = ProfileForm(request.POST or None, instance=profile, initial=initial)
    if request.method == "POST" and form.is_valid():
        profile = form.save(commit=False)
        profile.user = request.user
        profile.save()
        found = refresh_matches(profile)
        note = " We'll email you when new ones come in." if profile.alerts_on else ""
        messages.success(request, f"Profile saved. We found {found} jobs that fit you.{note}")
        return redirect("matches:list")
    return render(request, "matches/profile_form.html", {"form": form, "is_new": profile is None})


@login_required
def my_matches(request):
    profile = get_profile(request.user)
    if profile is None:
        messages.info(request, "First, tell us what work you do.")
        return redirect("matches:profile")
    matches = list(top_matches(profile, 50))
    add_personal_facts([m.contract for m in matches], profile)
    return render(request, "matches/match_list.html", {"profile": profile, "matches": matches})


@login_required
@require_POST
def refresh(request):
    profile = get_profile(request.user)
    if profile:
        found = refresh_matches(profile)
        messages.success(request, f"Updated. We found {found} jobs that fit you.")
    return redirect("matches:list")


def alerts_off(request, token):
    """The "Stop these emails" link. It asks first, so email link checkers can't turn alerts off."""
    profile = get_object_or_404(ContractorProfile, alert_token=token)
    if request.method == "POST":
        profile.alerts_on = False
        profile.save(update_fields=["alerts_on"])
        return render(request, "matches/alerts_off.html", {"done": True})
    return render(request, "matches/alerts_off.html", {"profile": profile})
