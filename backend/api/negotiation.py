from rest_framework.negotiation import BaseContentNegotiation, DefaultContentNegotiation


class JSONOnlyContentNegotiation(BaseContentNegotiation):
    """The API only speaks JSON: never answer 406 because of an Accept header."""

    def select_parser(self, request, parsers):
        return DefaultContentNegotiation().select_parser(request, parsers)

    def select_renderer(self, request, renderers, format_suffix=None):
        renderer = renderers[0]
        return renderer, renderer.media_type
