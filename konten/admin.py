from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Benutzer, Rolle


@admin.register(Benutzer)
class BenutzerAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "rolle", "is_active", "last_login")
    list_filter = ("rolle", "is_active")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Person", {"fields": ("first_name", "last_name", "email")}),
        ("Rolle und Status", {"fields": ("rolle", "is_active")}),
        ("Zeiten", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "first_name", "last_name", "rolle", "password1", "password2")}),
    )
    readonly_fields = ("last_login", "date_joined")

    def has_module_permission(self, request):
        return request.user.is_active and request.user.darf_verwalten

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        # Den Chef-Zugang darf nur der Chef selbst ändern (Rolle, Passwort, Sperre)
        if obj is not None and obj.rolle == Rolle.CHEF and not request.user.hat_rolle(Rolle.CHEF):
            return False
        return True

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        # Nur der Chef darf jemanden zum Chef machen
        if db_field.name == "rolle" and not request.user.hat_rolle(Rolle.CHEF):
            kwargs["choices"] = [(w, t) for w, t in Rolle.choices if w != Rolle.CHEF]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        # Benutzer werden deaktiviert, nicht gelöscht (Nachvollziehbarkeit)
        return False
