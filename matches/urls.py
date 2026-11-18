from django.urls import path

from . import views

app_name = "matches"

urlpatterns = [
    path("", views.my_matches, name="list"),
    path("profile/", views.edit_profile, name="profile"),
    path("refresh/", views.refresh, name="refresh"),
    path("alerts/off/<uuid:token>/", views.alerts_off, name="alerts_off"),
]
