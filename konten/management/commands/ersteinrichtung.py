"""Legt beim allerersten Start den Chef-Zugang an. Das Passwort tippt Chris selbst ein."""
import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from konten.models import Benutzer, Rolle


class Command(BaseCommand):
    help = "Ersten Benutzer (Chef) anlegen, falls noch keiner existiert."

    def handle(self, *args, **optionen):
        if Benutzer.objects.exists():
            self.stdout.write("Es gibt bereits Benutzer – nichts zu tun.")
            return
        self.stdout.write("\nERSTEINRICHTUNG PFALZ-WERK\nLegen Sie jetzt den Chef-Zugang an.\n")
        name = input("Benutzername: ").strip()
        if not name:
            raise CommandError("Kein Benutzername eingegeben.")
        vorname = input("Vorname: ").strip()
        nachname = input("Nachname: ").strip()
        while True:
            pw1 = getpass.getpass("Passwort (wird nicht angezeigt): ")
            pw2 = getpass.getpass("Passwort wiederholen: ")
            if pw1 != pw2:
                self.stdout.write("Die Passwörter stimmen nicht überein.")
                continue
            benutzer = Benutzer(username=name, first_name=vorname, last_name=nachname)
            try:
                validate_password(pw1, benutzer)
            except ValidationError as fehler:
                self.stdout.write(" ".join(fehler.messages))
                continue
            break
        benutzer.rolle = Rolle.CHEF
        benutzer.is_superuser = True
        benutzer.set_password(pw1)
        benutzer.save()
        self.stdout.write(self.style.SUCCESS(f"Chef-Zugang „{name}“ angelegt."))
