from django.contrib import admin

from .models import Agency, ApiCall, BidClick, Contract


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ["title", "place_state", "naics_code", "set_aside", "due_date", "active", "is_demo"]
    list_filter = ["active", "is_demo", "place_state", "notice_type"]
    search_fields = ["title", "notice_id", "solicitation_number"]


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ["name", "sub_tier", "office"]
    search_fields = ["name", "sub_tier", "office"]


@admin.register(ApiCall)
class ApiCallAdmin(admin.ModelAdmin):
    list_display = ["source", "status", "ok", "created_at", "endpoint"]
    list_filter = ["source", "ok"]


@admin.register(BidClick)
class BidClickAdmin(admin.ModelAdmin):
    list_display = ["contract", "user", "page", "created_at"]
    list_filter = ["page"]
