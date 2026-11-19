from django.urls import path

from . import ansichten as a

app_name = "zeiten"
urlpatterns = [
    path("", a.start, name="start"),
    path("meine/", a.meine, name="meine"),
    path("uebersicht/", a.uebersicht, name="uebersicht"),
    path("mitarbeiter/<int:pk>/", a.mitarbeiter, name="mitarbeiter"),
    path("mitarbeiter/<int:pk>/stundenzettel.pdf", a.stundenzettel, name="stundenzettel"),
    path("vertraege/", a.vertraege, name="vertraege"),
    path("vertraege/<int:pk>/", a.vertrag, name="vertrag"),
]
