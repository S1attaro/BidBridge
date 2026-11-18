from django.urls import path

from . import views

app_name = "summaries"

urlpatterns = [
    path("<str:notice_id>/", views.make_summary, name="make"),
]
