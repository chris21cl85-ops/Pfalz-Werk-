from django.urls import path

from . import views

app_name = "importe"
urlpatterns = [
    path("", views.uebersicht, name="uebersicht"),
    path("<int:pk>/", views.lauf, name="lauf"),
    path("<int:pk>/uebernehmen/", views.uebernehmen, name="uebernehmen"),
]
