"""Member-facing profile views plus the lightweight admin screen."""

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PhotoUploadForm, ProfileForm
from .models import Profile, ProfilePhoto


def get_or_create_profile(user) -> Profile:
    """Every signed-in member has exactly one profile row."""
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def browse(request):
    """The members list — the landing page after signing in."""
    my_profile = get_or_create_profile(request.user)

    # Only complete profiles are listed, so nobody sees an empty card.
    members = (
        Profile.objects.filter(published_at__isnull=False, user__is_active=True)
        .exclude(pk=my_profile.pk)
        .select_related("user")
        .prefetch_related("photos")
    )

    page = Paginator(members, 12).get_page(request.GET.get("page"))
    return render(request, "profiles/browse.html", {
        "page_obj": page,
        "my_profile": my_profile,
        "total_members": members.count(),
    })


def detail(request, pk):
    """Another member's profile."""
    profile = get_object_or_404(
        Profile.objects.select_related("user").prefetch_related("photos"),
        pk=pk, user__is_active=True,
    )
    # An incomplete profile is only visible to its owner.
    if profile.published_at is None and profile.user_id != request.user.id:
        messages.info(request, "That profile is not available.")
        return redirect("profiles:browse")

    return render(request, "profiles/detail.html", {
        "profile": profile,
        "photos": list(profile.photos.all()),
        "is_own": profile.user_id == request.user.id,
    })


def me(request):
    """The signed-in member's own profile, shown the way others see it."""
    profile = get_or_create_profile(request.user)
    return render(request, "profiles/detail.html", {
        "profile": profile,
        "photos": list(profile.photos.all()),
        "is_own": True,
    })


def edit(request):
    """Create or update the signed-in member's details and photos.

    Details and photos share one page but post to different endpoints, so
    uploading a photo never discards half-typed text and vice versa.
    """
    profile = get_or_create_profile(request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            profile.sync_published_state()
            messages.success(request, "Your profile has been saved.")
            return redirect("profiles:me" if profile.is_complete else "profiles:edit")
        messages.error(request, "Please correct the highlighted fields.")
    else:
        form = ProfileForm(instance=profile)

    return render(request, "profiles/edit.html", {
        "form": form,
        "profile": profile,
        "photos": list(profile.photos.all()),
        "photo_limit": settings.MAX_PHOTOS_PER_PROFILE,
        "max_photo_mb": settings.MAX_PHOTO_SIZE_MB,
    })


@require_POST
def upload_photos(request):
    """Receive a batch of photos from the drag-and-drop uploader.

    Answers JSON for the fetch()-based uploader and falls back to a redirect
    when JavaScript is unavailable.
    """
    profile = get_or_create_profile(request.user)
    form = PhotoUploadForm(request.POST, request.FILES, profile=profile)
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if form.is_valid():
        created = form.save()
        profile.sync_published_state()
        if wants_json:
            return JsonResponse({
                "ok": True,
                "photos": [
                    {"id": p.id, "url": p.image.url, "is_primary": p.is_primary}
                    for p in created
                ],
                "count": profile.photos.count(),
            })
        messages.success(request, f"{len(created)} photo(s) added.")
    else:
        errors = [msg for field in form.errors.values() for msg in field]
        if wants_json:
            return JsonResponse({"ok": False, "errors": errors}, status=400)
        for msg in errors:
            messages.error(request, msg)

    return redirect("profiles:edit")


@require_POST
def delete_photo(request, pk):
    """Remove one of the signed-in member's own photos."""
    # Filtering on the owner is what stops one member deleting another's photo.
    photo = get_object_or_404(ProfilePhoto, pk=pk, profile__user=request.user)
    photo.delete()
    request.user.profile.sync_published_state()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "Photo removed.")
    return redirect("profiles:edit")


@require_POST
def set_primary_photo(request, pk):
    """Choose which photo leads the profile."""
    photo = get_object_or_404(ProfilePhoto, pk=pk, profile__user=request.user)
    photo.make_primary()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "Main photo updated.")
    return redirect("profiles:edit")


# --------------------------------------------------------------------------
# Admin screen
# --------------------------------------------------------------------------


@staff_member_required
def admin_members(request):
    """A single screen listing every account, with a deactivate switch.

    Deliberately small: the brief asks only to view and deactivate accounts.
    The full Django admin remains available at /admin/ for anything else.
    """
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")

    profiles = (
        Profile.objects.select_related("user")
        .annotate(photo_count=Count("photos"))
        .order_by("-user__date_joined")
    )
    if query:
        profiles = profiles.filter(
            Q(user__email__icontains=query) | Q(full_name__icontains=query)
        )
    if status == "active":
        profiles = profiles.filter(user__is_active=True)
    elif status == "deactivated":
        profiles = profiles.filter(user__is_active=False)
    elif status == "unverified":
        profiles = profiles.filter(user__email_verified_at__isnull=True)

    page = Paginator(profiles, 25).get_page(request.GET.get("page"))
    all_profiles = Profile.objects.all()

    # Everything except `page`, so the pager keeps the current search/filter.
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "profiles/admin_members.html", {
        "page_obj": page,
        "query": query,
        "status": status,
        "querystring": params.urlencode(),
        "stats": {
            "total": all_profiles.count(),
            "active": all_profiles.filter(user__is_active=True).count(),
            "unverified": all_profiles.filter(user__email_verified_at__isnull=True).count(),
            "published": all_profiles.filter(published_at__isnull=False).count(),
        },
    })


@staff_member_required
@require_POST
def admin_toggle_active(request, pk):
    """Flip one account between active and deactivated."""
    profile = get_object_or_404(Profile.objects.select_related("user"), pk=pk)
    user = profile.user

    if user.is_superuser:
        messages.error(request, "Administrator accounts cannot be deactivated here.")
    else:
        user.is_active = not user.is_active
        user.deactivated_at = None if user.is_active else timezone.now()
        user.save(update_fields=["is_active", "deactivated_at"])
        state = "reactivated" if user.is_active else "deactivated"
        messages.success(request, f"{user.email} has been {state}.")

    # Preserve the current search / filter / page.
    return redirect(request.POST.get("next") or "profiles:admin_members")
