"""Vorheriger/nächster Eintrag in einer sortierten Liste – für die Blätterpfeile."""


def nachbarn(queryset, objekt):
    reihe = list(queryset.values_list("pk", flat=True))
    i = reihe.index(objekt.pk)
    modell = queryset.model
    return {
        "vorheriger": modell.objects.get(pk=reihe[i - 1]) if i > 0 else None,
        "naechster": modell.objects.get(pk=reihe[i + 1]) if i + 1 < len(reihe) else None,
        "position": i + 1,
        "gesamt": len(reihe),
    }


def aenderungen(formular):
    """Text „Feld: alt → neu“ für das Protokoll. Verweise (z. B. Kunde) erscheinen mit Namen."""
    zeilen = []
    for name in formular.changed_data:
        feld = formular.fields[name]
        alt = formular.initial.get(name)
        neu = formular.cleaned_data.get(name)
        if hasattr(feld, "queryset") and alt is not None and not hasattr(alt, "pk"):
            alt = feld.queryset.model.objects.filter(pk=alt).first()
        zeilen.append(f"{feld.label}: „{'' if alt is None else alt}“ → „{'' if neu is None else neu}“")
    return "\n".join(zeilen)
