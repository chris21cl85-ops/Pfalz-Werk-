from django.urls import path

from . import views

app_name = "sicherung"
urlpatterns = [
    path("", views.uebersicht, name="uebersicht"),
    path("anlegen/", views.anlegen, name="anlegen"),
]
