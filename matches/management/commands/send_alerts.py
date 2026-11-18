"""Email each user the new jobs that fit their profile. refresh_jobs runs this at the end.

    python manage.py send_alerts
"""

from django.core.management.base import BaseCommand

from matches.alerts import send_alert
from matches.models import ContractorProfile


class Command(BaseCommand):
    help = "Email new matching jobs to users who turned on alerts."

    def handle(self, *args, **opts):
        sent = 0
        profiles = ContractorProfile.objects.filter(alerts_on=True).exclude(alert_email="")
        for profile in profiles:
            try:
                if send_alert(profile):
                    sent += 1
            except OSError as e:
                self.stderr.write(f"Could not email {profile.alert_email}: {e}")
        self.stdout.write(f"Sent job alerts to {sent} of {profiles.count()} people.")
