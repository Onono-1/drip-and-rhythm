from __future__ import annotations

import os

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand

from apps.accounts.models import AdminRole, User
from apps.events.models import Event


class Command(BaseCommand):
    help = (
        "Idempotently ensure the singleton event exists and, if temporary bootstrap "
        "environment variables are provided and no super administrator exists yet, "
        "create the initial production super administrator without resetting existing accounts."
    )

    def handle(self, *args, **options):
        event = Event.get_current()
        self.stdout.write(
            self.style.SUCCESS(f"Event ready: {event.name} ({event.event_date.isoformat()})")
        )

        email = (os.getenv("INITIAL_SUPERADMIN_EMAIL") or "").strip().lower()
        password = os.getenv("INITIAL_SUPERADMIN_PASSWORD") or ""
        display_name = (os.getenv("INITIAL_SUPERADMIN_NAME") or "Super Admin").strip() or "Super Admin"

        if not email or not password:
            return

        if User.objects.filter(role=AdminRole.SUPER_ADMIN).exists():
            self.stdout.write(
                "Bootstrap skipped: a super administrator already exists. "
                "Remove INITIAL_SUPERADMIN_* environment variables from Render."
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                "Bootstrap skipped: account with INITIAL_SUPERADMIN_EMAIL already exists."
            )
            return

        validate_password(password)
        user = User.objects.create_superuser(
            email=email,
            password=password,
            display_name=display_name,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Bootstrapped initial super administrator: {user.email}. "
                "Remove INITIAL_SUPERADMIN_EMAIL and INITIAL_SUPERADMIN_PASSWORD from Render now."
            )
        )
