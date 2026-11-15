from django.urls import path

from . import eingang_ansichten as a

app_name = "eingang"
urlpatterns = [
    path("", a.liste, name="liste"),
    path("neu/", a.neu, name="neu"),
    path("<int:pk>/", a.detail, name="detail"),
    path("<int:pk>/zahlung/", a.zahlung, name="zahlung"),
    path("<int:pk>/stornieren/", a.stornieren, name="stornieren"),
    path("<int:pk>/beleg/", a.beleg, name="beleg"),
]
