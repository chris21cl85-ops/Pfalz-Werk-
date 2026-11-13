import datetime as dt
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook

from importe.models import Importlauf
from kern.models import Protokolleintrag
from konten.models import Rolle
from lieferanten.models import Lieferant
from material.models import Material
from mitarbeiter.importer import pin_schwaerzen
from mitarbeiter.models import Mitarbeiter
from tests.test_projekte_import import zeile

# ---------- Lieferanten (Oberfläche) ----------


@pytest.mark.django_db
def test_lieferant_anlegen_und_material_zeigen(chef_client):
    antwort = chef_client.post(reverse("lieferanten:neu"), {"name": "Holz Wickert", "plz": "67433", "aktiv": "on"},
                               follow=True)
    assert "wurde angelegt" in antwort.content.decode()
    l = Lieferant.objects.get()
    Material.objects.create(materialnr="M-1", bezeichnung="Spanplatte", lieferant=l)
    inhalt = chef_client.get(reverse("lieferanten:detail", args=[l.pk])).content.decode()
    assert "Spanplatte" in inhalt and "Material von diesem Lieferanten (1)" in inhalt
    assert Protokolleintrag.objects.filter(aktion="lieferant_angelegt").exists()


@pytest.mark.django_db
def test_lieferant_doppelt_abgelehnt(chef_client):
    Lieferant.objects.create(name="Wickert")
    antwort = chef_client.post(reverse("lieferanten:neu"), {"name": "wickert", "aktiv": "on"})
    assert "gibt es schon" in antwort.content.decode()


@pytest.mark.django_db
def test_lieferant_mit_material_nicht_loeschbar():
    from django.db.models import ProtectedError
    l = Lieferant.objects.create(name="Wickert")
    Material.objects.create(materialnr="M-1", bezeichnung="X", lieferant=l)
    with pytest.raises(ProtectedError):
        l.delete()


@pytest.mark.django_db
def test_material_formular_hat_lieferantenauswahl(chef_client):
    l = Lieferant.objects.create(name="Wickert")
    antwort = chef_client.post(reverse("material:neu"), {"materialnr": "M-5", "bezeichnung": "Kante",
                                                         "lieferant": l.pk, "aktiv": "on"})
    assert Material.objects.get(materialnr="M-5").lieferant == l


@pytest.mark.django_db
@pytest.mark.parametrize("rolle,erlaubt", [(Rolle.CHEF, True), (Rolle.MEISTER, True), (Rolle.BUCHHALTUNG, True),
                                           (Rolle.MITARBEITER, False)])
def test_lieferanten_rechte(client, benutzer_mit_rolle, rolle, erlaubt):
    client.force_login(benutzer_mit_rolle(rolle))
    assert (client.get(reverse("lieferanten:liste")).status_code == 200) is erlaubt


# ---------- Mitarbeiter (Oberfläche) ----------


@pytest.mark.django_db
def test_mitarbeiter_anlegen_mit_zugang(chef_client, benutzer_mit_rolle):
    zugang = benutzer_mit_rolle(Rolle.MITARBEITER, "kurt")
    antwort = chef_client.post(reverse("mitarbeiter:neu"), {
        "kuerzel": "kl", "name": "K.Laub", "rolle": "Geselle", "team_taeglich_verfuegbar": "on",
        "wochenstunden": "38,5", "stundensatz": "52,00", "benutzer": zugang.pk, "aktiv": "on"}, follow=True)
    assert "wurde angelegt" in antwort.content.decode()
    m = Mitarbeiter.objects.get()
    assert m.kuerzel == "KL" and m.wochenstunden == Decimal("38.5") and m.benutzer == zugang
    assert "52,00 €" in chef_client.get(reverse("mitarbeiter:detail", args=[m.pk])).content.decode()


@pytest.mark.django_db
def test_unplausible_wochenstunden(chef_client):
    antwort = chef_client.post(reverse("mitarbeiter:neu"), {"kuerzel": "X", "name": "X", "wochenstunden": "80", "aktiv": "on"})
    assert "Bitte prüfen" in antwort.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("rolle", [Rolle.MEISTER, Rolle.BUCHHALTUNG, Rolle.MITARBEITER])
def test_mitarbeiter_nur_chef_und_admin(client, benutzer_mit_rolle, rolle):
    client.force_login(benutzer_mit_rolle(rolle))
    assert client.get(reverse("mitarbeiter:liste")).status_code == 403


def test_pin_schwaerzen():
    assert pin_schwaerzen("Neutraler Startzugang · PIN dauerhaft 0000") == "Neutraler Startzugang · PIN dauerhaft ****"
    assert pin_schwaerzen("Meister") == "Meister"


# ---------- Import ----------


def mappe_bauen(tmp_path):
    mappe = Workbook()
    mappe.remove(mappe.active)
    ma = mappe.create_sheet("Mitarbeiter")
    ma.append(["TECHNISCHE KOMPATIBILITÄTSANSICHT"]); ma.append(["Navigation"])
    ma.append(["Kuerzel", "Name", "Rolle", "Team-taeglich verfuegbar", "Telefon", "Kann Montage leiten",
               "Hinweis", "Verfuegbarkeit", "Besonderheit", "Uhrzeit", "", "Anzeige", "Arbeitszeitmodell",
               "Einsatzmuster", "Abwesenheit / Einschränkung", "Freigabeberechtigt (auto)"])
    ma.append(["CL", "C.Lorenz", "Chef", "Ja", None, "Nein", "Systemeigentümer", "Vollzeit verfügbar",
               "Montag - Freitag", "07:00 - 12:00 & 12:45 - 15:45"])
    ma.append(["ADM", "Administrator", "Chef", "Ja", "+49 176 0000", "Nein",
               "Neutraler Startzugang · PIN dauerhaft 0000", "Vollzeit verfügbar", "Montag - Freitag", ""])
    ma.append(["WM", "W.Müller", "Geselle", "Ja", None, "Ja", None, "Vollzeit verfügbar", "Montag - Freitag", "",
               None, "WM – W.Müller", "Vollzeit 40 h", "Werkstatt + Montage", "Keine Überkopfarbeit", "Nein"])
    for _ in range(30):  # Formelzeilen ohne Person
        ma.append([None, None, None, None, None, None, None, "Vollzeit verfügbar", None, None, None, "–"])
    ds = mappe.create_sheet("Dashboard Steuerung")
    for _ in range(5):
        ds.append([])
    ds.append(zeile({"A": "CL", "B": "C.Lorenz", "M": "1234", "AB": dt.datetime(2020, 4, 1), "AD": 40, "AJ": 30}))
    ds.append(zeile({"A": "WM", "B": "W.Müller", "M": "9999", "AB": "01.09.2023", "AD": "38,5", "AJ": 28}))
    ds.append(zeile({"A": "XX", "B": "Unbekannt", "AD": 10}))
    mat = mappe.create_sheet("Material")
    mat.append(["Materialdatenbank"]); mat.append(["Nav"]); mat.append(["Material-ID"])
    mat.append(zeile({"A": "PL-1", "B": "Plattenwerkstoff", "C": "Dekor-Spanplatte 8 mm", "D": "m²", "E": 5.49, "G": "Wickert"}))
    mat.append(zeile({"A": "PL-2", "B": "Plattenwerkstoff", "C": "Dekor-Spanplatte 16 mm", "G": "wickert"}))
    mat.append(zeile({"A": "MDF-1", "B": "MDF", "C": "MDF roh", "G": "Holz Huber"}))
    pfad = tmp_path / "pw.xlsm"
    mappe.save(pfad)
    return pfad


def pruefen(client, pfad):
    client.post(reverse("importe:uebersicht"), {"datei": SimpleUploadedFile(pfad.name, pfad.read_bytes())})
    return Importlauf.objects.latest("zeitpunkt")


def blatt(lauf, name):
    return next(b for b in lauf.bericht["blaetter"] if b["blatt"] == name)


@pytest.mark.django_db(transaction=True)
def test_import_mitarbeiter_vertragsdaten_lieferanten(chef_client, tmp_path):
    lauf = pruefen(chef_client, mappe_bauen(tmp_path))
    assert blatt(lauf, "Mitarbeiter")["neu"] == 3
    assert blatt(lauf, "Mitarbeiter")["fehler"] == []  # Formelzeilen ohne Person zählen nicht
    assert blatt(lauf, "Dashboard Steuerung")["geaendert"] == 2
    assert "2 Lieferant(en) neu: Wickert, Holz Huber" in blatt(lauf, "Material")["zusatz"]
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))

    cl = Mitarbeiter.objects.get(kuerzel="CL")
    assert cl.rolle == "Chef" and cl.team_taeglich_verfuegbar and not cl.kann_montage_leiten
    assert cl.arbeitszeit.startswith("07:00") and cl.eintritt == dt.date(2020, 4, 1)
    assert cl.wochenstunden == 40 and cl.urlaubstage == 30
    wm = Mitarbeiter.objects.get(kuerzel="WM")
    assert wm.kann_montage_leiten and wm.wochenstunden == Decimal("38.5") and wm.eintritt == dt.date(2023, 9, 1)
    assert (wm.arbeitszeitmodell, wm.einsatzmuster, wm.einschraenkung) == (
        "Vollzeit 40 h", "Werkstatt + Montage", "Keine Überkopfarbeit")
    adm = Mitarbeiter.objects.get(kuerzel="ADM")
    assert "0000" not in adm.hinweise and "****" in adm.hinweise
    # PINs werden nirgends gespeichert
    for m in Mitarbeiter.objects.all():
        assert "1234" not in str(m.__dict__) and "9999" not in str(m.__dict__)

    assert Lieferant.objects.count() == 2
    assert Material.objects.get(materialnr="PL-2").lieferant.name == "Wickert"
    assert Material.objects.get(materialnr="MDF-1").lieferant.name == "Holz Huber"


@pytest.mark.django_db(transaction=True)
def test_lieferant_wird_bei_vorhandenem_material_ergaenzt_aber_nichts_ueberschrieben(chef_client, tmp_path):
    Material.objects.create(materialnr="PL-1", bezeichnung="Schon da", ek_netto=Decimal("99"))
    huber = Lieferant.objects.create(name="Holz Huber")
    Material.objects.create(materialnr="MDF-1", bezeichnung="Schon da", lieferant=Lieferant.objects.create(name="Anderer"))
    Mitarbeiter.objects.create(kuerzel="CL", name="C.Lorenz", wochenstunden=Decimal("35"))
    lauf = pruefen(chef_client, mappe_bauen(tmp_path))
    assert blatt(lauf, "Material")["geaendert"] == 1
    chef_client.post(reverse("importe:uebernehmen", args=[lauf.pk]))
    pl1 = Material.objects.get(materialnr="PL-1")
    assert pl1.lieferant.name == "Wickert" and pl1.ek_netto == 99 and pl1.bezeichnung == "Schon da"
    assert Material.objects.get(materialnr="MDF-1").lieferant.name == "Anderer"
    assert Mitarbeiter.objects.get(kuerzel="CL").wochenstunden == 35  # nicht überschrieben
    assert huber.material.count() == 0
