"""Email-verification links.

Rather than storing one-shot tokens in a table, links are signed with the
project SECRET_KEY. They expire on their own and cannot be forged, and there
is no extra model to keep clean.
"""

from django.conf import settings
from django.core import signing

# Namespace so a verification token can never be replayed as some other kind
# of signed value.
SALT = "accounts.email-verification"


def make_verification_token(user) -> str:
    """Sign a token that proves ownership of `user`'s current address."""
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=SALT)


def read_verification_token(token: str):
    """Return the payload dict, or None if the token is invalid or expired.

    The email is part of the payload so that changing an address invalidates
    any verification link that was sent to the old one.
    """
    max_age = settings.EMAIL_VERIFICATION_TIMEOUT_HOURS * 3600
    try:
        return signing.loads(token, salt=SALT, max_age=max_age)
    except signing.SignatureExpired:
        return None
    except signing.BadSignature:
        return None
