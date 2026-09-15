from django.core.management.base import BaseCommand

from apps.observability.services import pruning


class Command(BaseCommand):
    help = "Delete error log entries older than the configured retention window."

    def handle(self, *args, **options) -> None:
        days = pruning.retention_days()
        deleted = pruning.prune()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} error event(s) older than {days} day(s)."))
