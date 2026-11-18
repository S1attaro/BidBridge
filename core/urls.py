from django.urls import path

from contracts.views import ContractListView

from . import views

app_name = "core"

urlpatterns = [
    path("", ContractListView.as_view(), name="home"),
    path("signup/", views.signup, name="signup"),
    path("about/", views.about, name="about"),
]
