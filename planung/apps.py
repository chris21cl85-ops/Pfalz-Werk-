from django.apps import AppConfig


class PlanungConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "planung"
    verbose_name = "Montage & Kalender"

    def ready(self):
        from . import importer  # noqa: F401
