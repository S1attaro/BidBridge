from django.contrib import admin

from .models import AIRequestLog, ContractSummary


@admin.register(ContractSummary)
class ContractSummaryAdmin(admin.ModelAdmin):
    list_display = ["contract", "source", "model_name", "reading_grade", "created_at"]
    list_filter = ["source"]


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ["feature", "engine", "model_name", "latency_ms", "prompt_tokens", "completion_tokens", "ok", "created_at"]
    list_filter = ["feature", "engine", "ok"]
