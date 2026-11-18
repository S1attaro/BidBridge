from django.urls import path

from . import views

app_name = "saved"

urlpatterns = [
    path("", views.SavedListView.as_view(), name="list"),
    path("toggle/<str:notice_id>/", views.toggle_save, name="toggle"),
    path("<int:pk>/edit/", views.SavedUpdateView.as_view(), name="edit"),
    path("<int:pk>/remove/", views.SavedDeleteView.as_view(), name="delete"),
]
