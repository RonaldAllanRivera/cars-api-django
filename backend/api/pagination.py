import base64
import binascii
import json
import operator
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import reduce
from typing import Any
from urllib.parse import quote, urlencode

from django import forms
from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import BasePagination
from rest_framework.response import Response

POINTS_TO_NEXT = "_pointsToNextItems"


@dataclass(frozen=True)
class Cursor:
    """
    An opaque cursor: base64url JSON of the ordering columns of one row, plus
    which way it points. The encoding is part of the published API contract,
    so it stays stable for clients that hold a cursor across releases.
    """

    parameters: dict[str, Any]
    points_to_next: bool

    def encode(self) -> str:
        payload = json.dumps({**self.parameters, POINTS_TO_NEXT: self.points_to_next}, separators=(",", ":"))
        return base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()

    @classmethod
    def decode(cls, encoded: str) -> "Cursor | None":
        """None for anything malformed; the caller treats that as the first page."""
        try:
            raw = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        except (binascii.Error, ValueError):
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get(POINTS_TO_NEXT), bool):
            return None
        points_to_next = raw.pop(POINTS_TO_NEXT)
        return cls(raw, points_to_next)


def _cursor_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return value


class CursorEnvelopePagination(BasePagination):
    """
    Cursor pagination with the envelope the clients validate:

        {"data": [...], "links": {first, last, prev, next},
         "meta": {path, per_page, next_cursor, prev_cursor}}

    Views may set `cursor_ordering` (descending fields ending in a unique one,
    e.g. ("-occurred_at", "-id")). `per_page` outside 1..100 is a 422 rather
    than being silently clamped, so a client bug surfaces instead of hiding.
    """

    page_size = 24
    max_page_size = 100
    page_size_query_param = "per_page"
    cursor_query_param = "cursor"
    ordering: tuple[str, ...] = ("-id",)

    def paginate_queryset(self, queryset: QuerySet, request, view=None) -> list:
        self.request = request
        self.page_size = self.get_page_size(request)
        ordering = tuple(getattr(view, "cursor_ordering", None) or self.ordering)
        self.cursor = self.get_cursor(request, ordering)

        reverse = self.cursor is not None and not self.cursor.points_to_next
        if reverse:
            ordering = tuple(field[1:] if field.startswith("-") else f"-{field}" for field in ordering)
        self.fields = tuple(field.lstrip("-") for field in ordering)

        queryset = queryset.order_by(*ordering)
        if self.cursor is not None:
            queryset = queryset.filter(self._beyond(self.cursor, ordering))

        rows = list(queryset[: self.page_size + 1])
        self.has_more = len(rows) > self.page_size
        self.page = rows[: self.page_size]
        if reverse:
            self.page.reverse()
        return self.page

    def get_page_size(self, request) -> int:
        if self.page_size_query_param not in request.query_params:
            return self.page_size
        field = forms.IntegerField(min_value=1, max_value=self.max_page_size)
        try:
            return field.clean(request.query_params[self.page_size_query_param])
        except forms.ValidationError as exc:
            raise ValidationError({self.page_size_query_param: exc.messages}) from exc

    def get_cursor(self, request, ordering: tuple[str, ...]) -> Cursor | None:
        """The requested cursor, or None (first page) when absent or not for this ordering."""
        encoded = request.query_params.get(self.cursor_query_param)
        cursor = Cursor.decode(encoded) if encoded else None
        if cursor is None or any(field.lstrip("-") not in cursor.parameters for field in ordering):
            return None
        return cursor

    def _beyond(self, cursor: Cursor, ordering: tuple[str, ...]) -> Q:
        """Rows strictly after the cursor row in `ordering`: (a, b) < (va, vb), spelled out."""
        conditions = []
        equal_so_far = Q()
        for field in ordering:
            name = field.lstrip("-")
            value = self._parse(cursor.parameters[name])
            lookup = "lt" if field.startswith("-") else "gt"
            conditions.append(equal_so_far & Q(**{f"{name}__{lookup}": value}))
            equal_so_far &= Q(**{name: value})
        return reduce(operator.or_, conditions)

    @staticmethod
    def _parse(value: Any) -> Any:
        if isinstance(value, str) and (parsed := parse_datetime(value)) is not None:
            return parsed
        return value

    def next_cursor(self) -> Cursor | None:
        if not self.page or (not self.has_more and (self.cursor is None or self.cursor.points_to_next)):
            return None
        return self._cursor_for(self.page[-1], points_to_next=True)

    def previous_cursor(self) -> Cursor | None:
        if not self.page or self.cursor is None or (not self.cursor.points_to_next and not self.has_more):
            return None
        return self._cursor_for(self.page[0], points_to_next=False)

    def _cursor_for(self, row, points_to_next: bool) -> Cursor:
        return Cursor({field: _cursor_value(getattr(row, field)) for field in self.fields}, points_to_next)

    def _url(self, cursor: Cursor | None) -> str | None:
        """The current URL, query string kept, with the cursor replaced or appended."""
        if cursor is None:
            return None
        params = dict(self.request.query_params.items())
        params[self.cursor_query_param] = cursor.encode()
        return f"{self.request.build_absolute_uri(self.request.path)}?{urlencode(params, quote_via=quote)}"

    def get_paginated_response(self, data) -> Response:
        next_cursor, prev_cursor = self.next_cursor(), self.previous_cursor()
        return Response(
            {
                "data": data,
                "links": {"first": None, "last": None, "prev": self._url(prev_cursor), "next": self._url(next_cursor)},
                "meta": {
                    "path": self.request.build_absolute_uri(self.request.path),
                    "per_page": self.page_size,
                    "next_cursor": next_cursor.encode() if next_cursor else None,
                    "prev_cursor": prev_cursor.encode() if prev_cursor else None,
                },
            }
        )

    def get_paginated_response_schema(self, schema):
        return schema
