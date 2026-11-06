from django.contrib import admin

from .models import Importlauf


@admin.register(Importlauf)
class ImportlaufAdmin(admin.ModelAdmin):
    list_display = ("zeitpunkt", "dateiname", "status", "benutzer")
    readonly_fields = ("zeitpunkt", "benutzer", "dateiname", "gespeichert_als", "status", "bericht")

    def has_module_permission(self, request):
        return request.user.is_active and request.user.darf_verwalten

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
