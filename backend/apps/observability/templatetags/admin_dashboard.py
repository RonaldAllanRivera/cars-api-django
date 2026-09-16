from django import template

from apps.observability.services.dashboard import dashboard_metrics

register = template.Library()


@register.inclusion_tag("admin/pipeline_dashboard.html")
def pipeline_dashboard():
    return dashboard_metrics()
