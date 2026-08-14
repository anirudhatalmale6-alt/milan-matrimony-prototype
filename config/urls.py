"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"{settings.SITE_NAME} administration"
admin.site.site_title = f"{settings.SITE_NAME} admin"
admin.site.index_title = "Members and profiles"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("profiles.urls")),
]

if settings.DEBUG:
    # In production the uploads directory is served by the web server or
    # object storage; this is only for `runserver`.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
