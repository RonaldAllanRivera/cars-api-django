"""
Create or update the admin account from environment variables.

Runs on every container start (bin/start.sh) because Render's free tier has no
shell to run `createsuperuser` in. The environment is the source of truth: a
password changed in the admin UI is reset to ADMIN_PASSWORD on the next boot,
so change the variable rather than the UI.
"""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Idempotently create or update a superuser from ADMIN_EMAIL, ADMIN_PASSWORD and ADMIN_NAME."

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        name = os.environ.get("ADMIN_NAME", "").strip()

        if not email and not password:
            self.stdout.write("ensure_admin: ADMIN_EMAIL and ADMIN_PASSWORD are not set; skipping.")
            return
        if not email or not password:
            missing = "ADMIN_EMAIL" if not email else "ADMIN_PASSWORD"
            raise CommandError(
                f"ensure_admin: {missing} is not set. Set both ADMIN_EMAIL and ADMIN_PASSWORD, or neither."
            )

        User = get_user_model()
        email = User.objects.normalize_email(email)

        with transaction.atomic():
            user = User.objects.select_for_update().filter(email__iexact=email).first()
            created = user is None
            if created:
                user = User(email=email, name=name or email.split("@", 1)[0])

            try:
                validate_password(password, user)
            except ValidationError as exc:
                # The messages describe the rule that failed, never the password itself.
                raise CommandError("ensure_admin: ADMIN_PASSWORD rejected: " + " ".join(exc.messages)) from exc

            changed = created
            for field, value in (("is_staff", True), ("is_superuser", True), ("is_active", True)):
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if name and user.name != name:
                user.name = name
                changed = True
            if created or not user.check_password(password):
                user.set_password(password)
                changed = True

            if changed:
                user.save()

        outcome = "created" if created else ("updated" if changed else "unchanged")
        self.stdout.write(self.style.SUCCESS(f"ensure_admin: superuser {email} {outcome}."))
