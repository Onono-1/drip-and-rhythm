from __future__ import annotations

import os
import signal
import socket
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.communications.services import acquire_next_email_job, process_acquired_email_job


class Command(BaseCommand):
    help = "Run the independent native PostgreSQL-backed email delivery worker."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_requested = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Drain currently eligible email jobs once and exit.",
        )

    def _handle_signal(self, signum, _frame):
        self.stdout.write(self.style.WARNING(f"Received signal {signum}; shutting down email worker gracefully..."))
        self._stop_requested = True

    def handle(self, *args, **options):
        worker_id = f"{socket.gethostname()}-{os.getpid()}"
        run_once = bool(options["once"])
        poll_interval = float(settings.EMAIL_WORKER_POLL_INTERVAL)

        signal.signal(signal.SIGINT, self._handle_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._handle_signal)

        self.stdout.write(self.style.SUCCESS(f"Starting email worker [{worker_id}] (mode={settings.EMAIL_DELIVERY_MODE})"))

        processed = 0
        while not self._stop_requested:
            close_old_connections()
            job = acquire_next_email_job(worker_id)
            if job is not None:
                updated = process_acquired_email_job(job)
                processed += 1
                self.stdout.write(f"[{worker_id}] Job {updated.id} -> {updated.status}")
                continue

            if run_once:
                break

            time.sleep(poll_interval)

        self.stdout.write(self.style.SUCCESS(f"Email worker [{worker_id}] exited cleanly (processed={processed})."))
