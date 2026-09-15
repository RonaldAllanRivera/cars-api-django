"""Small HTML helpers shared by the Django admin modules."""

from urllib.parse import urlencode

from django.urls import reverse
from django.utils.html import format_html

# Readable on both the light and dark admin themes: white text on a saturated fill.
BADGE_COLORS = {
    "gray": "#6b7280",
    "blue": "#2563eb",
    "green": "#16a34a",
    "amber": "#d97706",
    "red": "#dc2626",
}


def badge(label: str, color: str = "gray"):
    return format_html(
        '<span style="display:inline-block;padding:1px 8px;border-radius:9999px;'
        'background:{};color:#fff;font-size:11px;font-weight:600;white-space:nowrap">{}</span>',
        BADGE_COLORS.get(color, BADGE_COLORS["gray"]),
        label,
    )


def thumbnail(thumbnail_url: str | None, source_url: str | None, *, height: int = 64):
    """Lazy-loaded Wikimedia thumbnail linking to the original.

    Never falls back to the original as the <img> source: originals are often
    several megabytes, and a changelist of 100 of them would stall the page.
    """
    if not thumbnail_url:
        if source_url:
            return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">original</a>', source_url)
        return "—"
    return format_html(
        '<a href="{}" target="_blank" rel="noopener noreferrer">'
        '<img src="{}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" '
        'style="height:{}px;width:{}px;object-fit:cover;border-radius:4px;display:block"></a>',
        source_url or thumbnail_url,
        thumbnail_url,
        height,
        round(height * 1.5),
    )


def admin_link(obj, label: str | None = None):
    """Link to an object's admin change page, or "—" for None."""
    if obj is None:
        return "—"
    opts = obj._meta
    url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
    return format_html('<a href="{}">{}</a>', url, label if label is not None else str(obj))


def changelist_url(app_label: str, model_name: str, **params) -> str:
    url = reverse(f"admin:{app_label}_{model_name}_changelist")
    return f"{url}?{urlencode(params)}" if params else url
