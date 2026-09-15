"""
/api/v1 routes. Paths carry no trailing slash, as the mobile client calls them.
A breaking change ships as /api/v2 beside this, never in place.
"""

from django.http import HttpRequest, JsonResponse
from django.urls import path, re_path
from rest_framework.routers import SimpleRouter

from api.v1 import views

app_name = "api"

router = SimpleRouter(trailing_slash=False, use_regex_path=False)
router.register("images", views.ImageViewSet, basename="images")
router.register("searches", views.SearchViewSet, basename="searches")
router.register("imports", views.ImportViewSet, basename="imports")


def not_found(request: HttpRequest, unmatched: str) -> JsonResponse:
    """API callers get JSON for an unknown route too, never the HTML 404 page."""
    return JsonResponse({"message": "Not found."}, status=404)


urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me", views.MeView.as_view(), name="auth-me"),
    *router.urls,
    path("exports", views.ExportCreateView.as_view(), name="exports-create"),
    path("health/summary", views.HealthSummaryView.as_view(), name="health-summary"),
    path("errors", views.ErrorListView.as_view(), name="errors-list"),
    re_path(r"^(?P<unmatched>.*)$", not_found),
]
