"""Django admin registration for profiles and photos."""

from django.contrib import admin
from django.utils.html import format_html

from .models import Profile, ProfilePhoto


class ProfilePhotoInline(admin.TabularInline):
    model = ProfilePhoto
    extra = 0
    fields = ("thumbnail", "image", "is_primary", "sort_order", "uploaded_at")
    readonly_fields = ("thumbnail", "uploaded_at")

    @admin.display(description="Preview")
    def thumbnail(self, obj):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="height:64px;border-radius:6px;object-fit:cover">',
            obj.image.url,
        )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user_email", "age", "location", "photo_count",
                    "is_published", "is_account_active")
    list_filter = ("gender", "marital_status", "published_at", "user__is_active")
    search_fields = ("full_name", "user__email", "city", "country")
    readonly_fields = ("created_at", "updated_at", "published_at")
    inlines = [ProfilePhotoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user").prefetch_related("photos")

    @admin.display(description="Email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Photos")
    def photo_count(self, obj):
        return obj.photos.count()

    @admin.display(description="Published", boolean=True)
    def is_published(self, obj):
        return obj.published_at is not None

    @admin.display(description="Account active", boolean=True)
    def is_account_active(self, obj):
        return obj.user.is_active


@admin.register(ProfilePhoto)
class ProfilePhotoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "profile", "is_primary", "uploaded_at")
    list_filter = ("is_primary", "uploaded_at")
    search_fields = ("profile__full_name", "profile__user__email")
