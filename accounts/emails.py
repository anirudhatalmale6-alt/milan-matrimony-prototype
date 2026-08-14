"""Outgoing mail for the accounts app."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .tokens import make_verification_token


def build_verification_url(user) -> str:
    """Absolute URL a member clicks to confirm their address."""
    path = reverse("accounts:verify_email", args=[make_verification_token(user)])
    return f"{settings.SITE_BASE_URL.rstrip('/')}{path}"


def send_verification_email(user) -> str:
    """Send the "confirm your email" message and return the link that was sent.

    Returning the URL keeps the tests (and the console backend during local
    development) from having to parse the message body.
    """
    context = {
        "user": user,
        "verification_url": build_verification_url(user),
        "site_name": settings.SITE_NAME,
        "expiry_hours": settings.EMAIL_VERIFICATION_TIMEOUT_HOURS,
    }
    subject = f"Confirm your email for {settings.SITE_NAME}"
    text_body = render_to_string("emails/verify_email.txt", context)
    html_body = render_to_string("emails/verify_email.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    # fail_silently: a temporarily unreachable SMTP server should not turn a
    # successful signup into a 500. The member can request a new link.
    message.send(fail_silently=True)
    return context["verification_url"]
