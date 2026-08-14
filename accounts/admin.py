"""Django admin registration for members."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Member list with verification state and bulk activate/deactivate."""

    list_display = ("email", "is_active", "email_verified_at", "date_joined", "is_staff")
    list_filter = ("is_active", "is_staff", "date_joined")
    search_fields = ("email",)
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login", "email_verified_at", "deactivated_at")

    # AbstractUser's fieldsets reference `username`, which this model drops.
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Status", {"fields": ("is_active", "email_verified_at", "deactivated_at")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_superuser")}),
    )

    actions = ["deactivate_members", "activate_members"]

    @admin.action(description="Deactivate selected members")
    def deactivate_members(self, request, queryset):
        updated = queryset.update(is_active=False, deactivated_at=timezone.now())
        self.message_user(request, f"{updated} member(s) deactivated.")

    @admin.action(description="Activate selected members")
    def activate_members(self, request, queryset):
        updated = queryset.update(is_active=True, deactivated_at=None)
        self.message_user(request, f"{updated} member(s) activated.")
