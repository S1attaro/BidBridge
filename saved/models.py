from django.conf import settings
from django.db import models

from contracts.models import Contract


class SavedContract(models.Model):
    STATUSES = [
        ("thinking", "Thinking about it"),
        ("bidding", "Working on a bid"),
        ("sent", "Bid sent"),
        ("won", "Won"),
        ("lost", "Didn't win"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_contracts")
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="saves")
    status = models.CharField(max_length=10, choices=STATUSES, default="thinking")
    note = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["contract__due_date"]
        constraints = [models.UniqueConstraint(fields=["user", "contract"], name="save_once")]

    def __str__(self):
        return f"{self.user} saved {self.contract.notice_id}"
