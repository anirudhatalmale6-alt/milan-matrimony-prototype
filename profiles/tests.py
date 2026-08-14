"""Tests for profile editing, photo upload and the admin screen."""

import io
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Profile, ProfilePhoto

User = get_user_model()

# Uploads in tests go to a throwaway directory, wiped in tearDownClass.
TEMP_MEDIA = tempfile.mkdtemp(prefix="milan-test-media-")


def make_image(width=2400, height=3000, fmt="JPEG", name="photo.jpg", color=(200, 120, 140)):
    """Build an in-memory upload of a given size and format."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format=fmt)
    buffer.seek(0)
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png"}[fmt]
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ProfileTestCase(TestCase):
    """Shared set-up: one signed-in, verified member."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(email="priya@example.com", password="x" * 12)
        self.user.mark_email_verified()
        self.client.force_login(self.user)

    def complete_details(self, **overrides):
        data = {
            "full_name": "Priya Sharma",
            "date_of_birth": "1996-04-12",
            "gender": "F",
            "height_cm": "165",
            "marital_status": "never",
            "religion": "Hindu",
            "community": "",
            "mother_tongue": "Marathi",
            "city": "Pune",
            "country": "India",
            "education": "B.E. Computer Science",
            "occupation": "Software Engineer",
            "about": "Hello.",
        }
        data.update(overrides)
        return data


class ProfileEditTests(ProfileTestCase):
    def test_saving_required_fields_publishes_the_profile(self):
        response = self.client.post(reverse("profiles:edit"), self.complete_details())
        self.assertRedirects(response, reverse("profiles:me"))

        profile = Profile.objects.get(user=self.user)
        self.assertTrue(profile.is_complete)
        self.assertIsNotNone(profile.published_at)
        self.assertEqual(profile.age, date.today().year - 1996 - (
            (date.today().month, date.today().day) < (4, 12)))

    def test_missing_required_field_keeps_the_profile_unpublished(self):
        response = self.client.post(reverse("profiles:edit"),
                                    self.complete_details(city=""))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(Profile.objects.get(user=self.user).published_at)

    def test_under_eighteen_is_rejected(self):
        recent = date.today().replace(year=date.today().year - 16).isoformat()
        response = self.client.post(reverse("profiles:edit"),
                                    self.complete_details(date_of_birth=recent))
        self.assertContains(response, "at least 18")

    def test_incomplete_profiles_are_hidden_from_the_members_list(self):
        other = User.objects.create_user(email="other@example.com", password="x" * 12)
        other.mark_email_verified()
        Profile.objects.create(user=other)  # nothing filled in

        response = self.client.get(reverse("profiles:browse"))
        self.assertNotContains(response, "other@example.com")
        self.assertEqual(len(response.context["page_obj"].object_list), 0)

    def test_a_deactivated_members_profile_is_not_reachable(self):
        other = User.objects.create_user(email="other@example.com", password="x" * 12)
        profile = Profile.objects.create(user=other, full_name="Anita Rao",
                                         date_of_birth=date(1994, 1, 1),
                                         gender="F", city="Mumbai")
        profile.sync_published_state()
        other.is_active = False
        other.save(update_fields=["is_active"])

        response = self.client.get(reverse("profiles:detail", args=[profile.pk]))
        self.assertEqual(response.status_code, 404)


class PhotoUploadTests(ProfileTestCase):
    def upload(self, *files):
        return self.client.post(reverse("profiles:upload_photos"), {"images": list(files)},
                                HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_multiple_photos_upload_in_one_request(self):
        response = self.upload(make_image(name="a.jpg"), make_image(name="b.jpg"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProfilePhoto.objects.count(), 2)

    def test_first_photo_becomes_the_primary_one(self):
        self.upload(make_image(name="a.jpg"))
        self.upload(make_image(name="b.jpg"))

        photos = list(ProfilePhoto.objects.order_by("uploaded_at"))
        self.assertTrue(photos[0].is_primary)
        self.assertFalse(photos[1].is_primary)

    def test_large_photos_are_resized_and_re_encoded(self):
        self.upload(make_image(width=4000, height=5000, name="huge.jpg"))
        photo = ProfilePhoto.objects.get()

        with Image.open(photo.image.path) as stored:
            self.assertLessEqual(max(stored.size), 1600)
            self.assertEqual(stored.format, "JPEG")

    def test_png_uploads_are_converted_to_jpeg(self):
        self.upload(make_image(fmt="PNG", name="shot.png"))
        photo = ProfilePhoto.objects.get()
        self.assertTrue(photo.image.name.endswith(".jpg"))

    def test_non_image_files_are_rejected(self):
        bad = SimpleUploadedFile("notes.jpg", b"this is not an image",
                                 content_type="image/jpeg")
        response = self.upload(bad)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProfilePhoto.objects.count(), 0)

    def test_the_photo_limit_is_enforced(self):
        with override_settings(MAX_PHOTOS_PER_PROFILE=2):
            self.upload(make_image(name="a.jpg"), make_image(name="b.jpg"))
            response = self.upload(make_image(name="c.jpg"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProfilePhoto.objects.count(), 2)

    def test_oversized_files_are_rejected_before_being_stored(self):
        with override_settings(MAX_PHOTO_SIZE_MB=0):
            response = self.upload(make_image(name="a.jpg"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProfilePhoto.objects.count(), 0)

    def test_choosing_a_new_main_photo_demotes_the_old_one(self):
        self.upload(make_image(name="a.jpg"), make_image(name="b.jpg"))
        second = ProfilePhoto.objects.order_by("uploaded_at")[1]

        self.client.post(reverse("profiles:set_primary_photo", args=[second.pk]))

        self.assertEqual(ProfilePhoto.objects.filter(is_primary=True).count(), 1)
        second.refresh_from_db()
        self.assertTrue(second.is_primary)

    def test_deleting_the_main_photo_promotes_another(self):
        self.upload(make_image(name="a.jpg"), make_image(name="b.jpg"))
        first = ProfilePhoto.objects.order_by("uploaded_at")[0]

        self.client.post(reverse("profiles:delete_photo", args=[first.pk]))

        self.assertEqual(ProfilePhoto.objects.count(), 1)
        self.assertTrue(ProfilePhoto.objects.get().is_primary)

    def test_a_member_cannot_delete_someone_elses_photo(self):
        other = User.objects.create_user(email="other@example.com", password="x" * 12)
        other_profile = Profile.objects.create(user=other)
        victim = ProfilePhoto.objects.create(profile=other_profile,
                                             image=make_image(name="theirs.jpg"))

        response = self.client.post(reverse("profiles:delete_photo", args=[victim.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProfilePhoto.objects.filter(pk=victim.pk).exists())


class AdminScreenTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(email="admin@example.com", password="x" * 12,
                                              is_staff=True)
        self.staff.mark_email_verified()
        self.member_profile = Profile.objects.create(
            user=self.user, full_name="Priya Sharma", date_of_birth=date(1996, 4, 12),
            gender="F", city="Pune",
        )
        self.member_profile.sync_published_state()

    def test_ordinary_members_cannot_open_the_admin_screen(self):
        response = self.client.get(reverse("profiles:admin_members"))
        # staff_member_required bounces non-staff to the admin login.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_can_view_and_deactivate_an_account(self):
        self.client.force_login(self.staff)

        listing = self.client.get(reverse("profiles:admin_members"))
        self.assertContains(listing, "priya@example.com")

        self.client.post(
            reverse("profiles:admin_toggle_active", args=[self.member_profile.pk])
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIsNotNone(self.user.deactivated_at)

    def test_deactivation_can_be_reversed(self):
        self.client.force_login(self.staff)
        url = reverse("profiles:admin_toggle_active", args=[self.member_profile.pk])

        self.client.post(url)
        self.client.post(url)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNone(self.user.deactivated_at)

    def test_superusers_cannot_be_deactivated_from_this_screen(self):
        root = User.objects.create_superuser(email="root@example.com", password="x" * 12)
        root_profile = Profile.objects.create(user=root)
        self.client.force_login(self.staff)

        self.client.post(reverse("profiles:admin_toggle_active", args=[root_profile.pk]))

        root.refresh_from_db()
        self.assertTrue(root.is_active)
