from django.contrib import admin

from .models import ContractorProfile, Match


@admin.register(ContractorProfile)
class ContractorProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "business_name", "states", "updated_at"]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["profile", "contract", "score", "method", "created_at"]
