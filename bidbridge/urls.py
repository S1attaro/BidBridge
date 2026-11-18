from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("core.urls")),
    path("contracts/", include("contracts.urls")),
    path("api/", include("contracts.api_urls")),
    path("summary/", include("summaries.urls")),
    path("matches/", include("matches.urls")),
    path("saved/", include("saved.urls")),
]
