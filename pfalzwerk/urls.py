from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from kern import views as kern

admin.site.site_header = "PFALZ-WERK Verwaltung"
admin.site.site_title = "PFALZ-WERK"
admin.site.index_title = "Verwaltung"

urlpatterns = [
    path("", kern.startseite, name="startseite"),
    path("anmelden/", auth_views.LoginView.as_view(template_name="konten/anmelden.html"), name="anmelden"),
    path("abmelden/", auth_views.LogoutView.as_view(), name="abmelden"),
    path("passwort/", auth_views.PasswordChangeView.as_view(
        template_name="konten/passwort.html", success_url="/passwort/fertig/"), name="passwort"),
    path("passwort/fertig/", auth_views.PasswordChangeDoneView.as_view(
        template_name="konten/passwort_fertig.html"), name="passwort_fertig"),
    path("protokoll/", kern.protokoll, name="protokoll"),
    path("sicherung/", include("sicherung.urls")),
    path("import/", include("importe.urls")),
    path("kunden/", include("kunden.urls")),
    path("projekte/", include("projekte.urls")),
    path("material/", include("material.urls")),
    path("verwaltung/", admin.site.urls),
]
