"""User model for the platform.

The site has a single role — a registered user — so the model stays small:
email instead of a username, plus the flags the admin screen needs.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Manager for a user model keyed on email rather than username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # A superuser is created from the command line, so there is no
        # verification email to click — mark it verified up front.
        extra_fields.setdefault("email_verified_at", timezone.now())
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """A registered member.

    `is_active` is reserved for the admin's deactivate switch, so email
    verification is tracked separately by `email_verified_at`. That way an
    account that was deactivated by an admin and an account that simply has
    not confirmed its address stay distinguishable.
    """

    # AbstractUser ships a username field; this site does not use one.
    username = None
    email = models.EmailField("email address", unique=True)
    email_verified_at = models.DateTimeField(
        "email verified at", null=True, blank=True,
        help_text="Set when the member clicks the link in their verification email.",
    )
    deactivated_at = models.DateTimeField(
        "deactivated at", null=True, blank=True,
        help_text="Set when an administrator deactivates the account.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "member"
        verbose_name_plural = "members"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    def mark_email_verified(self):
        """Record a successful verification. Safe to call more than once."""
        if self.email_verified_at is None:
            self.email_verified_at = timezone.now()
            self.save(update_fields=["email_verified_at"])

    @property
    def display_name(self) -> str:
        """Best available human label — the profile name, else the email."""
        profile = getattr(self, "profile", None)
        if profile and profile.full_name:
            return profile.full_name
        return self.email.split("@")[0]
