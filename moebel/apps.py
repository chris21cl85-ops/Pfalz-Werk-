from django.apps import AppConfig


class MoebelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "moebel"
    verbose_name = "Möbelrechner"

    def ready(self):
        from . import importer  # noqa: F401
