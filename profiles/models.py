"""Member profiles and their photos."""

import uuid
from datetime import date

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


def photo_upload_path(instance, filename: str) -> str:
    """Store each photo under its owner's folder with a random name.

    A random name means an uploaded file cannot overwrite another one and the
    original filename (which often carries the uploader's real name) is not
    exposed in the URL.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"
    return f"profiles/{instance.profile_id}/{uuid.uuid4().hex}.{ext}"


class Profile(models.Model):
    """The public-facing details of one member.

    Created automatically (blank) the first time a member reaches their
    profile page, so a `user.profile` always exists for a signed-in member.
    """

    class Gender(models.TextChoices):
        WOMAN = "F", "Woman"
        MAN = "M", "Man"
        OTHER = "O", "Other"

    class MaritalStatus(models.TextChoices):
        NEVER_MARRIED = "never", "Never married"
        DIVORCED = "divorced", "Divorced"
        WIDOWED = "widowed", "Widowed"
        SEPARATED = "separated", "Separated"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    full_name = models.CharField(max_length=120, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    height_cm = models.PositiveSmallIntegerField(
        "height (cm)", null=True, blank=True,
        validators=[MinValueValidator(120), MaxValueValidator(230)],
    )
    marital_status = models.CharField(
        max_length=16, choices=MaritalStatus.choices, blank=True
    )
    religion = models.CharField(max_length=60, blank=True)
    community = models.CharField(max_length=60, blank=True,
                                 help_text="Caste, sub-community or denomination.")
    mother_tongue = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, blank=True)
    education = models.CharField(max_length=120, blank=True)
    occupation = models.CharField(max_length=120, blank=True)
    about = models.TextField("about me", max_length=2000, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Stamped the first time the profile has enough detail to be listed.
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.full_name or self.user.email

    def get_absolute_url(self):
        return reverse("profiles:detail", args=[self.pk])

    # -- completeness ------------------------------------------------------

    #: Fields a profile needs before it appears in the members list.
    REQUIRED_FIELDS = ("full_name", "date_of_birth", "gender", "city")

    @property
    def is_complete(self) -> bool:
        return all(getattr(self, field) for field in self.REQUIRED_FIELDS)

    @property
    def completeness_percent(self) -> int:
        """Rough progress figure used by the "complete your profile" nudge."""
        tracked = self.REQUIRED_FIELDS + (
            "height_cm", "marital_status", "religion", "mother_tongue",
            "country", "education", "occupation", "about",
        )
        filled = sum(1 for field in tracked if getattr(self, field))
        score = filled / (len(tracked) + 1)  # +1 for "has at least one photo"
        if self.photos.exists():
            score += 1 / (len(tracked) + 1)
        return int(round(score * 100))

    def sync_published_state(self):
        """Keep `published_at` in step with whether the profile is complete."""
        if self.is_complete and self.published_at is None:
            self.published_at = timezone.now()
            self.save(update_fields=["published_at"])
        elif not self.is_complete and self.published_at is not None:
            self.published_at = None
            self.save(update_fields=["published_at"])

    # -- derived display values -------------------------------------------

    @property
    def age(self):
        """Age in whole years, or None if no date of birth is set."""
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def height_display(self) -> str:
        """Height as "170 cm (5'7")" — both units, since audiences differ."""
        if not self.height_cm:
            return ""
        total_inches = round(self.height_cm / 2.54)
        return f"{self.height_cm} cm ({total_inches // 12}'{total_inches % 12}\")"

    @property
    def location(self) -> str:
        return ", ".join(part for part in (self.city, self.country) if part)

    @property
    def primary_photo(self):
        """The chosen main photo, falling back to the first uploaded one."""
        return self.photos.filter(is_primary=True).first() or self.photos.first()

    @property
    def initials(self) -> str:
        """Placeholder avatar text for profiles with no photo yet."""
        parts = [p for p in self.full_name.split() if p]
        if not parts:
            return self.user.email[:1].upper()
        return (parts[0][:1] + (parts[-1][:1] if len(parts) > 1 else "")).upper()


class ProfilePhoto(models.Model):
    """One uploaded photo belonging to a profile."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=photo_upload_path)
    caption = models.CharField(max_length=120, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "sort_order", "uploaded_at"]

    def __str__(self):
        return f"Photo #{self.pk} of {self.profile}"

    def make_primary(self):
        """Promote this photo, demoting whichever one held the slot."""
        self.profile.photos.exclude(pk=self.pk).filter(is_primary=True).update(is_primary=False)
        if not self.is_primary:
            self.is_primary = True
            self.save(update_fields=["is_primary"])

    def delete(self, *args, **kwargs):
        """Delete the row and the file, then re-elect a primary if needed."""
        profile, was_primary = self.profile, self.is_primary
        # Remove the file from storage; Django only deletes the DB row.
        self.image.delete(save=False)
        super().delete(*args, **kwargs)
        if was_primary:
            replacement = profile.photos.first()
            if replacement:
                replacement.make_primary()
