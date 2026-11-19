from django.urls import path

from . import ansichten as a

app_name = "planung"
urlpatterns = [
    path("", a.kalender, name="kalender"),
    path("kapazitaet/", a.kapazitaet, name="kapazitaet"),
    path("teams/", a.teams, name="teams"),
    path("teams/<int:pk>/", a.team, name="team"),
    path("abwesenheiten/", a.abwesenheiten, name="abwesenheiten"),
    path("montageplan/", a.montageplan, name="montageplan"),
    path("montage/<int:pk>/", a.montage, name="montage"),
]
