"""Job alert emails: new jobs that fit a user's profile, sent after each refresh."""

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .matching import score_contracts

MAX_JOBS = 10
# Skip jobs that close too soon to bid on.
MIN_DAYS_LEFT = 2


def new_jobs_for(profile, since):
    """Matching jobs that showed up on BidBridge after `since`, best fit first."""
    jobs = []
    for score, sim, contract, reason in score_contracts(profile):
        if contract.created <= since:
            continue
        if contract.days_left is None or contract.days_left < MIN_DAYS_LEFT:
            continue
        contract.reason = reason
        jobs.append(contract)
    return jobs[:MAX_JOBS]


def send_alert(profile, now=None):
    """Email new jobs to one user. Returns how many jobs were in the email (0 means no email)."""
    now = now or timezone.now()
    since = profile.last_alert_at or now - timedelta(days=1)
    jobs = new_jobs_for(profile, since)
    profile.last_alert_at = now
    profile.save(update_fields=["last_alert_at"])
    if not jobs:
        return 0

    context = {
        "jobs": jobs,
        "site": settings.SITE_URL,
        "matches_url": settings.SITE_URL + reverse("matches:list"),
        "stop_url": settings.SITE_URL + reverse("matches:alerts_off", args=[profile.alert_token]),
    }
    subject = f"{len(jobs)} new job{'s' if len(jobs) != 1 else ''} for you on BidBridge"
    send_mail(
        subject,
        render_to_string("matches/alert_email.txt", context),
        settings.DEFAULT_FROM_EMAIL,
        [profile.alert_email],
        html_message=render_to_string("matches/alert_email.html", context),
    )
    return len(jobs)
