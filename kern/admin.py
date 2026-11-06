from django.contrib import admin

from .models import Protokolleintrag


@admin.register(Protokolleintrag)
class ProtokollAdmin(admin.ModelAdmin):
    list_display = ("zeitpunkt", "benutzername", "aktion", "gegenstand")
    list_filter = ("aktion",)
    search_fields = ("benutzername", "gegenstand", "details")

    def has_module_permission(self, request):
        return request.user.is_active and request.user.darf_verwalten

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
