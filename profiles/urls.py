"""Profile and admin-screen URLs."""

from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("", views.browse, name="browse"),
    path("me/", views.me, name="me"),
    path("me/edit/", views.edit, name="edit"),
    path("me/photos/upload/", views.upload_photos, name="upload_photos"),
    path("me/photos/<int:pk>/delete/", views.delete_photo, name="delete_photo"),
    path("me/photos/<int:pk>/primary/", views.set_primary_photo, name="set_primary_photo"),
    path("members/<int:pk>/", views.detail, name="detail"),

    # Minimal staff screen (the full Django admin lives at /admin/).
    path("manage/members/", views.admin_members, name="admin_members"),
    path("manage/members/<int:pk>/toggle/", views.admin_toggle_active,
         name="admin_toggle_active"),
]
