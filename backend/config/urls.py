from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView

from api.v1.views import ExportDownloadView


def up(request):
    return JsonResponse({"status": "ok"})


admin.site.site_header = "Cars Images API"
admin.site.site_title = "Cars Images API"
admin.site.index_title = "Pipeline administration"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False), name="home"),
    path("admin/", admin.site.urls),
    path("up", up, name="up"),
    path("api/v1/", include("api.urls")),
    # Outside /api: the system browser follows this signed link with no bearer token.
    path("exports/download", ExportDownloadView.as_view(), name="exports-download"),
]
