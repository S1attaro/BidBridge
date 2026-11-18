from django.contrib import admin

from .models import SavedContract


@admin.register(SavedContract)
class SavedContractAdmin(admin.ModelAdmin):
    list_display = ["user", "contract", "status", "created_at"]
    list_filter = ["status"]
