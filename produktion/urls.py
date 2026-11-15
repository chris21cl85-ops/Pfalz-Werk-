from django.urls import path

from . import ansichten as a

app_name = "produktion"
urlpatterns = [
    path("", a.uebersicht, name="uebersicht"),
    path("meine/", a.meine, name="meine"),
    path("bibliothek/", a.bibliothek, name="bibliothek"),
    path("projekt/<int:pk>/", a.projekt, name="projekt"),
    path("arbeitsgang/<int:pk>/", a.bearbeiten, name="bearbeiten"),
]
