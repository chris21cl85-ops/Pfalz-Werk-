from django.contrib.auth.models import AbstractUser
from django.db import models


class Rolle(models.TextChoices):
    CHEF = "chef", "Chef"
    ADMIN = "admin", "Admin"
    BUCHHALTUNG = "buchhaltung", "Buchhaltung"
    MEISTER = "meister", "Meister"
    MITARBEITER = "mitarbeiter", "Mitarbeiter"


# Rollen, die Benutzer verwalten und Sicherungen auslösen dürfen
VERWALTUNGS_ROLLEN = {Rolle.CHEF, Rolle.ADMIN}


class Benutzer(AbstractUser):
    """Anmeldbarer Mensch im Betrieb. Passwörter speichert Django nur gehasht."""

    rolle = models.CharField(max_length=20, choices=Rolle.choices, default=Rolle.MITARBEITER)

    class Meta:
        verbose_name = "Benutzer"
        verbose_name_plural = "Benutzer"

    def hat_rolle(self, *rollen) -> bool:
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return self.rolle in rollen

    @property
    def darf_verwalten(self) -> bool:
        return self.hat_rolle(*VERWALTUNGS_ROLLEN)

    def save(self, *args, **kwargs):
        # Chef und Admin dürfen die Benutzerverwaltung öffnen
        self.is_staff = self.is_superuser or self.rolle in VERWALTUNGS_ROLLEN
        super().save(*args, **kwargs)

    def __str__(self):
        name = self.get_full_name() or self.username
        return f"{name} ({self.get_rolle_display()})"
