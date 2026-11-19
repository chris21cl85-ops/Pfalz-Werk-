from django.urls import path

from . import ansichten as a

app_name = "inventur"
urlpatterns = [
    path("", a.liste, name="liste"),
    path("<int:pk>/", a.detail, name="detail"),
    path("<int:pk>/bericht.pdf", a.bericht, name="bericht"),
]
