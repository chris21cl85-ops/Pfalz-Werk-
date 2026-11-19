from django.urls import path

from . import ansichten as a

app_name = "moebel"
urlpatterns = [
    path("", a.liste, name="liste"),
    path("neu/", a.neu, name="neu"),
    path("regeln/", a.regeln, name="regeln"),
    path("<int:pk>/", a.detail, name="detail"),
    path("<int:pk>/bearbeiten/", a.bearbeiten, name="bearbeiten"),
    path("<int:pk>/teileliste.pdf", a.pdf, name="pdf"),
    path("<int:pk>/etiketten.pdf", a.etiketten, name="etiketten"),
]
