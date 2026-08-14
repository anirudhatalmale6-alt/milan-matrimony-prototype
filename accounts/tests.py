"""Tests for sign-up, email verification and the guest lock-out."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .tokens import make_verification_token

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SignUpTests(TestCase):
    url = None

    def setUp(self):
        self.url = reverse("accounts:signup")

    def test_signup_creates_unverified_user_and_sends_one_email(self):
        response = self.client.post(self.url, {
            "email": "Priya@Example.com",
            "password1": "strong-passphrase-1",
            "password2": "strong-passphrase-1",
            "accept_terms": "on",
        })
        self.assertRedirects(response, reverse("accounts:signup_done"))

        user = User.objects.get()
        # Addresses are stored lower-cased so logins are case-insensitive.
        self.assertEqual(user.email, "priya@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/verify/", mail.outbox[0].body)

    def test_duplicate_email_is_rejected_regardless_of_case(self):
        User.objects.create_user(email="priya@example.com", password="x" * 12)
        response = self.client.post(self.url, {
            "email": "PRIYA@example.com",
            "password1": "strong-passphrase-1",
            "password2": "strong-passphrase-1",
            "accept_terms": "on",
        })
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post(self.url, {
            "email": "a@example.com",
            "password1": "strong-passphrase-1",
            "password2": "different-passphrase",
            "accept_terms": "on",
        })
        self.assertContains(response, "do not match")
        self.assertEqual(User.objects.count(), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class VerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="priya@example.com", password="x" * 12)

    def test_valid_link_verifies_and_signs_in(self):
        url = reverse("accounts:verify_email", args=[make_verification_token(self.user)])
        response = self.client.get(url)

        self.assertRedirects(response, reverse("profiles:edit"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_tampered_token_is_refused(self):
        url = reverse("accounts:verify_email", args=["not-a-real-token"])
        self.assertEqual(self.client.get(url).status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_link_stops_working_once_the_address_changes(self):
        token = make_verification_token(self.user)
        self.user.email = "new@example.com"
        self.user.save(update_fields=["email"])

        response = self.client.get(reverse("accounts:verify_email", args=[token]))
        self.assertEqual(response.status_code, 400)

    def test_expired_link_is_refused(self):
        token = make_verification_token(self.user)
        # Zero-hour lifetime makes any token immediately too old.
        with override_settings(EMAIL_VERIFICATION_TIMEOUT_HOURS=0):
            response = self.client.get(reverse("accounts:verify_email", args=[token]))
        self.assertEqual(response.status_code, 400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="priya@example.com", password="x" * 12)
        self.url = reverse("accounts:login")

    def test_unverified_user_cannot_sign_in(self):
        response = self.client.post(self.url, {"username": "priya@example.com",
                                               "password": "x" * 12})
        self.assertRedirects(response, self.url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verified_user_can_sign_in_with_any_casing(self):
        self.user.mark_email_verified()
        response = self.client.post(self.url, {"username": "PRIYA@example.com",
                                               "password": "x" * 12})
        self.assertRedirects(response, reverse("profiles:browse"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_deactivated_user_cannot_sign_in(self):
        self.user.mark_email_verified()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(self.url, {"username": "priya@example.com",
                                               "password": "x" * 12})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "do not match an account")


class GuestLockOutTests(TestCase):
    """The brief requires that guests see nothing at all."""

    def test_member_pages_redirect_guests_to_login(self):
        for name in ["profiles:browse", "profiles:me", "profiles:edit"]:
            with self.subTest(view=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response, f"{reverse('accounts:login')}?next={reverse(name)}"
                )

    def test_a_member_profile_is_not_readable_by_url(self):
        response = self.client.get(reverse("profiles:detail", args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_public_pages_stay_reachable(self):
        for name in ["accounts:login", "accounts:signup", "accounts:password_reset"]:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
