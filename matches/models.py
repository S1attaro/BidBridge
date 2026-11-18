import uuid

from django.conf import settings
from django.db import models

from contracts import codes
from contracts.models import Contract


class ContractorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    business_name = models.CharField(max_length=120, blank=True)
    trades = models.JSONField(default=list)
    services = models.CharField(max_length=300, blank=True)
    states = models.JSONField(default=list)
    zip_code = models.CharField(max_length=5, blank=True)
    is_small = models.BooleanField(default=True)
    set_asides = models.JSONField(default=list, blank=True)
    alerts_on = models.BooleanField(default=False)
    alert_email = models.EmailField(blank=True)
    alert_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    last_alert_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name or self.user.username

    @property
    def state_names(self):
        return [codes.STATE_NAMES.get(s, s) for s in self.states]

    @property
    def trade_names(self):
        return [codes.TRADES[t][0] for t in self.trades if t in codes.TRADES]

    @property
    def naics_codes(self):
        return [c for t in self.trades for c in codes.naics_codes(t)]

    def can_bid(self, set_aside_code):
        group = codes.set_aside_group(set_aside_code)
        if group in (None, "none"):
            return True
        if group == "small":
            return self.is_small
        if group == "vosb" and "sdvosb" in self.set_asides:
            return True
        return group in self.set_asides


class Match(models.Model):
    profile = models.ForeignKey(ContractorProfile, on_delete=models.CASCADE, related_name="matches")
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="matches")
    score = models.FloatField()
    similarity = models.FloatField(default=0)
    reason = models.CharField(max_length=400)
    method = models.CharField(max_length=20, default="keywords")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score"]
        constraints = [models.UniqueConstraint(fields=["profile", "contract"], name="match_once")]

    def __str__(self):
        return f"{self.profile} - {self.contract.notice_id} ({self.score:.2f})"
