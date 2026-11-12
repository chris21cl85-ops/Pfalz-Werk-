from django.urls import path

from . import ansichten

app_name = "material"
urlpatterns = [
    path("", ansichten.liste, name="liste"),
    path("neu/", ansichten.neu, name="neu"),
    path("<int:pk>/", ansichten.detail, name="detail"),
    path("<int:pk>/bearbeiten/", ansichten.bearbeiten, name="bearbeiten"),
]
