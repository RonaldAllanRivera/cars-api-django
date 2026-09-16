"""Seed common makes and models. Safe to run repeatedly."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import CarMake, CarModel

CATALOG: dict[str, list[str]] = {
    "Toyota": ["Corolla", "Camry", "RAV4", "Hilux"],
    "Honda": ["Civic", "Accord", "CR-V", "Jazz"],
    "Tesla": ["Model 3", "Model Y", "Model S", "Model X"],
    "Ford": ["Mustang", "F-150", "Focus", "Explorer"],
    "BMW": ["3 Series", "5 Series", "X3", "X5"],
    "Mercedes-Benz": ["A-Class", "C-Class", "E-Class", "GLC"],
    "Nissan": ["Altima", "Sentra", "X-Trail"],
    "Hyundai": ["Elantra", "Tucson", "Santa Fe"],
    "Kia": ["Sportage", "Sorento", "Rio"],
    "Volkswagen": ["Golf", "Passat", "Tiguan"],
}


class Command(BaseCommand):
    help = "Create the default car makes and models. Existing rows are left untouched."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Do nothing when any make already exists (used on container start, so makes "
            "deleted in the admin are not re-created on every boot).",
        )

    def handle(self, *args, if_empty=False, **options):
        if if_empty and CarMake.objects.exists():
            self.stdout.write("seed_catalog: catalog already has makes; skipping.")
            return

        with transaction.atomic():
            makes_before = CarMake.objects.count()
            models_before = CarModel.objects.count()
            # Two bulk inserts instead of one round trip per row: this runs at boot
            # against a remote database, where each query costs tens of milliseconds.
            CarMake.objects.bulk_create([CarMake(name=name) for name in CATALOG], ignore_conflicts=True)
            make_ids = dict(CarMake.objects.filter(name__in=CATALOG).values_list("name", "id"))
            CarModel.objects.bulk_create(
                [CarModel(make_id=make_ids[make], name=model) for make, models in CATALOG.items() for model in models],
                ignore_conflicts=True,
            )
            makes_added = CarMake.objects.count() - makes_before
            models_added = CarModel.objects.count() - models_before

        self.stdout.write(self.style.SUCCESS(f"seed_catalog: added {makes_added} makes and {models_added} models."))
