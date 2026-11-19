from django.core.management.base import BaseCommand

from handy import netz


class Command(BaseCommand):
    help = "Zeile 1: Adresse für runserver; Zeile 2 (nur wenn Handy im WLAN an ist): Adresse für Handys."

    def handle(self, *args, **optionen):
        self.stdout.write(netz.bindeadresse())
        if netz.an():
            self.stdout.write(netz.handy_adresse())
