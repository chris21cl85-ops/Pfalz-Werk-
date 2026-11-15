from django.urls import path

from . import ansichten as a

app_name = "lager"
urlpatterns = [
    path("", a.uebersicht, name="uebersicht"),
    path("vorschlag/", a.vorschlag_bestellen, name="vorschlag"),
    path("bestellungen/", a.bestellungen, name="bestellungen"),
    path("bestellungen/neu/", a.neu, name="neu"),
    path("bestellungen/<int:pk>/", a.bestellung, name="bestellung"),
    path("bestand/", a.bestandsliste, name="bestand"),
    path("bestand/<int:pk>/", a.lagerkarte, name="lagerkarte"),
]
