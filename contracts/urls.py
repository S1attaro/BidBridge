from django.urls import path

from . import views

app_name = "contracts"

urlpatterns = [
    path("", views.ContractListView.as_view(), name="list"),
    path("<str:notice_id>/", views.ContractDetailView.as_view(), name="detail"),
    path("<str:notice_id>/calendar.ics", views.calendar_file, name="calendar"),
    path("<str:notice_id>/bid-click/", views.bid_click, name="bid_click"),
]
