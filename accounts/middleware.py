"""Site-wide login gate."""

from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, reverse, Resolver404


class LoginRequiredMiddleware:
    """Require a signed-in member for every page except an explicit allow-list.

    The brief calls for no guest access at all, so the default is "closed" and
    each public page has to opt in via settings.PUBLIC_URL_NAMES. Adding a new
    view therefore cannot accidentally leak content to anonymous visitors.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.public_names = set(settings.PUBLIC_URL_NAMES)

    def __call__(self, request):
        if not self._is_exempt(request):
            login_url = reverse(settings.LOGIN_URL)
            return redirect(f"{login_url}?next={request.get_full_path()}")
        return self.get_response(request)

    def _is_exempt(self, request) -> bool:
        if request.user.is_authenticated:
            return True

        path = request.path_info
        # Static and uploaded files are served by the web server / WhiteNoise
        # and never pass through the view layer in production; in DEBUG they
        # do, so skip them explicitly.
        if path.startswith((settings.STATIC_URL, settings.MEDIA_URL, "/static/", "/media/")):
            return True
        # The Django admin has its own login screen.
        if path.startswith("/admin/"):
            return True

        try:
            match = resolve(path)
        except Resolver404:
            # Let Django raise its own 404 rather than bouncing to login.
            return True

        return match.view_name in self.public_names
