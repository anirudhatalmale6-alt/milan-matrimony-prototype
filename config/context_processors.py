"""Template context shared by every page."""

from django.conf import settings


def branding(request):
    """Expose the configurable site name and tagline to all templates."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
    }
