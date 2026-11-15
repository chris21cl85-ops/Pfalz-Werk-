"""Startwerte: Arbeitsgangbibliothek und drei Standard-Routen wie in der Excel."""
from django.db import migrations


def anlegen(apps, schema_editor):
    from produktion.stamm import BIBLIOTHEK, ROUTEN
    Vorlage = apps.get_model("produktion", "Vorlage")
    Route = apps.get_model("produktion", "Route")
    Routenschritt = apps.get_model("produktion", "Routenschritt")
    namen = {}
    for code, kat, name, typ, folge, qm, warte in BIBLIOTHEK:
        Vorlage.objects.get_or_create(code=code, defaults={"kategorie": kat, "name": name, "typ": typ,
                                                           "standardfolge": folge, "qm_danach": qm,
                                                           "wartezeit_moeglich": warte})
        namen[code] = (name, typ)
    for rname, gruppe, schritte in ROUTEN:
        route, neu = Route.objects.get_or_create(name=rname, defaults={"werkstoffgruppe": gruppe})
        if not neu:
            continue
        for i, (code, std, warte, hinweis) in enumerate(schritte, start=1):
            name, typ = namen[code]
            Routenschritt.objects.create(route=route, schritt=i, code=code, name=name, typ=typ, plan_std=std,
                                         wartezeit_std=warte, hinweis=hinweis)


class Migration(migrations.Migration):
    dependencies = [("produktion", "0001_initial")]
    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
