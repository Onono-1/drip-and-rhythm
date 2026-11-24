from django.core.management.base import BaseCommand

from apps.events.models import Event


class Command(BaseCommand):
    help = "Ensure the DRIP & RHYTHM singleton event configuration exists."

    def handle(self, *args, **options):
        event = Event.get_current()
        self.stdout.write(self.style.SUCCESS(f"Event ready: {event.name} ({event.event_date.isoformat()})"))
