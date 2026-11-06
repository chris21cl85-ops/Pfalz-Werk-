from django.core.management.base import BaseCommand

from sicherung.dienst import sicherung_anlegen, sicherung_wenn_faellig


class Command(BaseCommand):
    help = "Datensicherung anlegen."

    def add_arguments(self, parser):
        parser.add_argument("--wenn-faellig", action="store_true",
                            help="Nur sichern, wenn heute noch keine Sicherung existiert.")

    def handle(self, *args, wenn_faellig=False, **optionen):
        pfad = sicherung_wenn_faellig() if wenn_faellig else sicherung_anlegen(anlass="Befehl")
        if pfad is None:
            self.stdout.write("Heute wurde bereits gesichert.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Sicherung angelegt: {pfad}"))
