from django.urls import path

from . import ansichten as a

app_name = "auswertung"
urlpatterns = [
    path("", a.uebersicht, name="uebersicht"),
    path("projekt/<int:pk>/", a.projekt, name="projekt"),
]
