from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Zeigt, wo PFALZ-WERK seine Daten und Sicherungen speichert."

    def handle(self, *args, **optionen):
        self.stdout.write(f"Daten und Sicherungen liegen in: {settings.LOKAL_DIR}")
