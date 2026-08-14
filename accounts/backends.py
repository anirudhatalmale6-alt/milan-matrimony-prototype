"""Authentication backend."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class EmailBackend(ModelBackend):
    """Authenticate on a case-insensitive email address.

    Django's default backend looks up USERNAME_FIELD exactly as typed. People
    type their address with inconsistent casing, so we normalise it here.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username or kwargs.get("email")
        if email is None or password is None:
            return None
        try:
            user = UserModel.objects.get(email__iexact=email.strip())
        except UserModel.DoesNotExist:
            # Run the hasher anyway so a missing account and a wrong password
            # take the same amount of time (avoids user enumeration).
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
