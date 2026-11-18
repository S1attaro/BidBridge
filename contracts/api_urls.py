from django.urls import path

from . import api

app_name = "api"

urlpatterns = [
    path("contracts/", api.contract_list, name="contracts"),
    path("contracts/<str:notice_id>/", api.contract_detail, name="contract"),
]
