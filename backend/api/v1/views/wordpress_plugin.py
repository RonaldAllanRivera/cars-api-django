from django.http import HttpRequest, HttpResponse
from django.views import View
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasAbility, IsStaff
from api.v1 import plugin_links
from apps.accounts import abilities
from apps.publishing.services import wordpress_plugin


class WordPressPluginLinkView(APIView):
    """A signed, single-use link to the plugin zip, for staff who set up WordPress publishing."""

    permission_classes = [IsAuthenticated, HasAbility, IsStaff]
    required_ability = abilities.BLOG_WRITE
    throttle_scope = "write"

    def post(self, request: Request) -> Response:
        url, expires_at = plugin_links.mint(request)
        version = wordpress_plugin.plugin_version()
        return Response(
            {
                "url": url,
                "expires_at": expires_at.isoformat(),
                "filename": f"{wordpress_plugin.SLUG}-{version}.zip",
                "version": version,
            }
        )


class WordPressPluginDownloadView(View):
    """Serves a signed plugin link. Errors are plain text because a browser tab shows them."""

    def get(self, request: HttpRequest) -> HttpResponse:
        outcome = plugin_links.redeem(request.GET.get("token", ""))
        if outcome == plugin_links.INVALID:
            return _plain("This download link is invalid or has expired. Download again from the app.", 403)
        if outcome == plugin_links.USED:
            return _plain("This download link has already been used. Download again from the app.", 410)

        package = wordpress_plugin.build_package()
        return HttpResponse(
            package.data,
            content_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{package.filename}"',
                "Cache-Control": "no-store",
            },
        )


def _plain(message: str, status: int) -> HttpResponse:
    return HttpResponse(message, status=status, content_type="text/plain; charset=utf-8")
