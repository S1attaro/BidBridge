from django.db import models

from contracts.models import Contract


class ContractSummary(models.Model):
    SOURCES = [("ai", "AI summary"), ("simple", "Simple summary")]

    contract = models.OneToOneField(Contract, on_delete=models.CASCADE, related_name="summary")
    summary = models.TextField()
    job = models.CharField(max_length=200, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    skills = models.JSONField(default=list, blank=True)
    key_dates = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=10, choices=SOURCES)
    model_name = models.CharField(max_length=80, blank=True)
    used_full_text = models.BooleanField(default=False)
    reading_grade = models.FloatField(null=True, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_source_display()} for {self.contract.notice_id}"


class AIRequestLog(models.Model):
    """One row per AI call. Used for speed and cost numbers in the evaluation."""

    feature = models.CharField(max_length=30)
    engine = models.CharField(max_length=30)
    model_name = models.CharField(max_length=80, blank=True)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    latency_ms = models.IntegerField(default=0)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.feature} {self.engine} {self.latency_ms} ms"
