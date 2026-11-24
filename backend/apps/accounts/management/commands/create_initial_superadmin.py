from __future__ import annotations

import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import AdminRole, User
from apps.events.models import Event


class Command(BaseCommand):
    help = "Create or update an initial super administrator securely without hardcoded credentials."

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, default=os.getenv("INITIAL_SUPERADMIN_EMAIL", ""))
        parser.add_argument("--display-name", type=str, default=os.getenv("INITIAL_SUPERADMIN_NAME", "Super Admin"))
        parser.add_argument(
            "--password-env",
            type=str,
            default="INITIAL_SUPERADMIN_PASSWORD",
            help="Environment variable containing the password for non-interactive runs.",
        )

    def handle(self, *args, **options):
        Event.get_current()
        email = (options["email"] or "").strip().lower()
        if not email:
            email = input("Super administrator email: ").strip().lower()
        if not email:
            raise CommandError("Email is required.")

        display_name = (options["display_name"] or "Super Admin").strip()
        password = os.getenv(options["password_env"], "")
        if not password:
            password = getpass.getpass("Super administrator password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise CommandError("Passwords did not match.")

        validate_password(password)

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "display_name": display_name,
                "role": AdminRole.SUPER_ADMIN,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.display_name = display_name
        user.role = AdminRole.SUPER_ADMIN
        user.is_active = True
        user.set_password(password)
        user.save()

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} super administrator: {user.email}"))
