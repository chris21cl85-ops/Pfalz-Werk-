"""Teams, Abwesenheiten, Montageplan und Termine wie Blätter „Teams“, „Zeitdaten“, „Montageplan“, „Zeitplan“."""
from django.conf import settings
from django.db import models

TEAMARTEN = ["Werkstatt", "Montage", "Arbeitsvorbereitung", "Service", "Gemischt"]
FAHRZEUGE = ["Transporter", "PKW", "Anhänger"]


class Team(models.Model):
    teamid = models.CharField("Team-ID", max_length=20, unique=True)
    name = models.CharField("Teamname", max_length=100, unique=True)
    art = models.CharField("Teamart", max_length=30, choices=[(a, a) for a in TEAMARTEN], default="Montage")
    aktiv = models.BooleanField("Aktiv", default=True)
    hinweis = models.CharField("Aufgaben / Hinweis", max_length=250, blank=True)
    angelegt_am = models.DateField("Angelegt am", auto_now_add=True)

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def mitglieder(self):
        """Aktive Mitglieder (wie Mitglieder(): Zuordnung aktiv = Ja), Leitung zuerst."""
        return [z.mitarbeiter for z in self.zuordnungen.filter(aktiv=True).select_related("mitarbeiter")
                .order_by("-leitung", "mitarbeiter__name")]


class TeamMitglied(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="zuordnungen")
    mitarbeiter = models.ForeignKey("mitarbeiter.Mitarbeiter", on_delete=models.PROTECT, related_name="team_zuordnungen")
    leitung = models.BooleanField("Leitung", default=False)
    aktiv = models.BooleanField("Zuordnung aktiv", default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["team", "mitarbeiter"], name="mitglied_einmal_je_team")]


class Abwesenheit(models.Model):
    class Art(models.TextChoices):
        URLAUB = "Urlaub", "Urlaub"
        KRANK = "Krank", "Krank"
        FORTBILDUNG = "Fortbildung", "Fortbildung"
        BERUFSSCHULE = "Berufsschule", "Berufsschule"
        ZEITAUSGLEICH = "Zeitausgleich", "Zeitausgleich"
        SONSTIGES = "Sonstiges", "Sonstiges"

    class Status(models.TextChoices):
        BEANTRAGT = "Beantragt", "Beantragt"
        FREIGEGEBEN = "Freigegeben", "Freigegeben"
        ABGELEHNT = "Abgelehnt", "Abgelehnt"

    zid = models.CharField("Zeit-ID", max_length=20, unique=True)
    mitarbeiter = models.ForeignKey("mitarbeiter.Mitarbeiter", on_delete=models.PROTECT, related_name="abwesenheiten")
    von = models.DateField("Von")
    bis = models.DateField("Bis")
    art = models.CharField("Zeitart", max_length=20, choices=Art.choices, default=Art.URLAUB)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.BEANTRAGT)
    hinweis = models.CharField("Hinweis", max_length=250, blank=True)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")
    erfasst_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abwesenheit"
        verbose_name_plural = "Abwesenheiten"
        ordering = ["-von", "mitarbeiter__name"]

    def __str__(self):
        return f"{self.zid} {self.mitarbeiter} {self.art} {self.von:%d.%m.}–{self.bis:%d.%m.%Y}"

    @property
    def tage(self) -> int:
        return (self.bis - self.von).days + 1


class Montage(models.Model):
    """Eine Zeile im Montageplan je Projekt (Termin ändern = dieselbe Zeile neu planen)."""

    class Ergebnis(models.TextChoices):
        OFFEN = "", "offen"
        BESTANDEN = "Bestanden", "Bestanden"
        NACHARBEIT = "Nacharbeit erforderlich", "Nacharbeit erforderlich"

    projekt = models.OneToOneField("projekte.Projekt", on_delete=models.PROTECT, related_name="montage")
    adresse = models.CharField("Baustelle / Adresse", max_length=250, blank=True)
    datum = models.DateField("Datum")
    beginn = models.TimeField("Beginn")
    ende = models.TimeField("Ende")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, related_name="montagen")
    aufgaben = models.CharField("Aufgaben", max_length=300, blank=True)
    material = models.CharField("Material", max_length=250, blank=True)
    werkzeug = models.CharField("Werkzeug", max_length=250, blank=True)
    fahrzeug = models.CharField("Fahrzeug", max_length=60, blank=True)
    hinweise = models.CharField("Hinweise", max_length=300, blank=True)
    ergebnis = models.CharField("Montageergebnis", max_length=30, choices=Ergebnis.choices, blank=True, default="")
    ergebnis_am = models.DateTimeField("Ergebnis am", null=True, blank=True)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Montage"
        verbose_name_plural = "Montageplan"
        ordering = ["datum", "beginn"]

    def __str__(self):
        return f"Montage {self.projekt.projektnr} {self.datum:%d.%m.%Y}"


class Termin(models.Model):
    """Zeile im Zeitplan: ein Mitarbeiter, ein Tag, eine Aufgabe."""

    class Art(models.TextChoices):
        MONTAGE = "Montage", "Montage"
        WERKSTATT = "Werkstatt", "Werkstatt"
        KUNDE = "Kundentermin", "Kundentermin"
        AUFMASS = "Aufmaß", "Aufmaß"
        SONSTIGES = "Sonstiges", "Sonstiges"

    terminid = models.CharField("Termin-ID", max_length=20, unique=True)
    mitarbeiter = models.ForeignKey("mitarbeiter.Mitarbeiter", on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="termine")
    datum = models.DateField("Datum")
    beginn = models.TimeField("Start", null=True, blank=True)
    ende = models.TimeField("Ende", null=True, blank=True)
    projekt = models.ForeignKey("projekte.Projekt", on_delete=models.PROTECT, null=True, blank=True, related_name="termine")
    aufgabe = models.CharField("Aufgabe", max_length=200)
    ort = models.CharField("Ort", max_length=200, blank=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="termine")
    art = models.CharField("Terminart", max_length=20, choices=Art.choices, default=Art.SONSTIGES)
    aus_montage = models.BooleanField("aus dem Montageplan", default=False)
    abgesagt = models.BooleanField("Abgesagt", default=False)
    erfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")

    class Meta:
        verbose_name = "Termin"
        verbose_name_plural = "Zeitplan"
        ordering = ["datum", "beginn"]

    def __str__(self):
        return f"{self.terminid} {self.datum:%d.%m.%Y} {self.aufgabe}"
