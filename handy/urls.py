from django.urls import path

from . import ansichten as a

app_name = "handy"
urlpatterns = [
    path("", a.start, name="start"),
    path("tag/", a.tag, name="tag"),
    path("arbeit/", a.arbeit, name="arbeit"),
    path("zeit/", a.zeit, name="zeit"),
    path("zaehlen/", a.zaehlen, name="zaehlen"),
    path("lieferungen/", a.lieferungen, name="lieferungen"),
    path("freigaben/", a.freigaben, name="freigaben"),
    path("melden/", a.melden, name="melden"),
    path("meldungen/", a.meldungen, name="meldungen"),
    path("meldungen/<int:pk>/foto/", a.foto, name="foto"),
    path("zuschnitt/", a.zuschnitt, name="zuschnitt"),
    path("zuschnitt/<int:pk>/", a.zuschnitt_detail, name="zuschnitt_detail"),
    path("verbinden/", a.verbinden, name="verbinden"),
]
