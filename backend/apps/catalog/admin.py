from django.contrib import admin
from django.db.models import Count

from apps.catalog.models import CarMake, CarModel


class CarModelInline(admin.TabularInline):
    model = CarModel
    extra = 0
    fields = ("name", "created_at")
    readonly_fields = ("created_at",)


@admin.register(CarMake)
class CarMakeAdmin(admin.ModelAdmin):
    list_display = ("name", "models_count", "created_at")
    search_fields = ("name", "models__name")
    readonly_fields = ("created_at", "updated_at")
    fields = ("name", "created_at", "updated_at")
    inlines = [CarModelInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(models_count=Count("models"))

    @admin.display(description="Models", ordering="models_count")
    def models_count(self, obj):
        return obj.models_count
