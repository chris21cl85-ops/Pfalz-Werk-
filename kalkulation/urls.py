from django.urls import path

from . import ansichten as a

app_name = "kalkulation"
urlpatterns = [
    path("", a.liste, name="liste"),
    path("projekt/<int:pk>/", a.projekt, name="projekt"),
]
