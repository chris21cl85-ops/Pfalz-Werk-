from django.urls import path

from . import finanzen_ansichten as a

app_name = "finanzen"
urlpatterns = [
    path("", a.uebersicht, name="uebersicht"),
    path("datev/", a.datev, name="datev"),
]
