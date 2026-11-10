from django.apps import AppConfig


class ProjekteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "projekte"
    verbose_name = "Projekte"

    def ready(self):
        from . import importer  # noqa: F401
