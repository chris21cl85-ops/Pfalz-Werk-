from django.urls import path

from . import ansichten

app_name = "rechnungen"
urlpatterns = [
    path("", ansichten.liste, name="liste"),
    path("neu/", ansichten.neu, name="neu"),
    path("firmendaten/", ansichten.firmendaten, name="firmendaten"),
    path("<int:pk>/", ansichten.detail, name="detail"),
    path("<int:pk>/bearbeiten/", ansichten.bearbeiten, name="bearbeiten"),
    path("<int:pk>/festschreiben/", ansichten.festschreiben, name="festschreiben"),
    path("<int:pk>/verwerfen/", ansichten.verwerfen, name="verwerfen"),
    path("<int:pk>/pdf/", ansichten.pdf, name="pdf"),
    path("<int:pk>/xrechnung/", ansichten.xml, name="xml"),
    path("<int:pk>/zahlung/", ansichten.zahlung, name="zahlung"),
    path("zahlung/<int:pk>/gegenbuchung/", ansichten.gegenbuchung, name="gegenbuchung"),
]
