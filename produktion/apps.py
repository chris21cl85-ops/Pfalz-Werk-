from django.apps import AppConfig


class ProduktionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "produktion"
    verbose_name = "Produktion"

    def ready(self):
        from . import importer  # noqa: F401
