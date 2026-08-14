"""Profile editing and photo upload forms."""

from datetime import date

from django import forms
from django.conf import settings

from .imaging import process_upload
from .models import Profile, ProfilePhoto


class ProfileForm(forms.ModelForm):
    """The single "my details" form."""

    class Meta:
        model = Profile
        fields = [
            "full_name", "date_of_birth", "gender", "height_cm", "marital_status",
            "religion", "community", "mother_tongue", "city", "country",
            "education", "occupation", "about",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "e.g. Priya Sharma"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "height_cm": forms.NumberInput(attrs={"placeholder": "e.g. 165", "min": 120,
                                                  "max": 230}),
            "religion": forms.TextInput(attrs={"placeholder": "e.g. Hindu"}),
            "community": forms.TextInput(attrs={"placeholder": "e.g. Brahmin"}),
            "mother_tongue": forms.TextInput(attrs={"placeholder": "e.g. Marathi"}),
            "city": forms.TextInput(attrs={"placeholder": "e.g. Pune"}),
            "country": forms.TextInput(attrs={"placeholder": "e.g. India"}),
            "education": forms.TextInput(attrs={"placeholder": "e.g. B.E. Computer Science"}),
            "occupation": forms.TextInput(attrs={"placeholder": "e.g. Software Engineer"}),
            "about": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "A few lines about you, your family and what you are "
                               "looking for in a partner.",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # HTML date inputs only accept ISO format; without this an existing
        # value renders in the locale format and shows up blank.
        self.fields["date_of_birth"].input_formats = ["%Y-%m-%d"]
        for name in Profile.REQUIRED_FIELDS:
            if name in self.fields:
                self.fields[name].required = True
        self.fields["gender"].empty_label = "Select"
        self.fields["marital_status"].empty_label = "Select"

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise forms.ValidationError("You must be at least 18 years old to register.")
        if age > 100:
            raise forms.ValidationError("Please check the date of birth you entered.")
        return dob

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Please enter your full name.")
        return name


class MultiFileInput(forms.ClearableFileInput):
    """File input that accepts several files at once."""

    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    """FileField that cleans every file in a multi-file selection.

    Django's FileField validates a single upload; with `multiple` set, the
    widget hands over a list, so each entry is validated individually and the
    field always returns a list.
    """

    widget = MultiFileInput

    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data]
        return [clean_one(data, initial)]


class PhotoUploadForm(forms.Form):
    """Accepts a batch of photos from one drag-and-drop selection."""

    images = MultiFileField(
        widget=MultiFileInput(attrs={"multiple": True,
                                     "accept": "image/jpeg,image/png,image/webp"}),
        label="Photos",
    )

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)

    def clean_images(self):
        files = self.cleaned_data["images"]
        if not files:
            raise forms.ValidationError("Please choose at least one photo.")

        remaining = settings.MAX_PHOTOS_PER_PROFILE - self.profile.photos.count()
        if remaining <= 0:
            raise forms.ValidationError(
                f"You already have the maximum of {settings.MAX_PHOTOS_PER_PROFILE} photos. "
                "Delete one to make room."
            )
        if len(files) > remaining:
            raise forms.ValidationError(
                f"You can add {remaining} more photo(s) — you selected {len(files)}."
            )

        # Re-encode every file up front so a bad one fails the whole submission
        # cleanly instead of leaving half a batch saved.
        processed = []
        for uploaded in files:
            processed.append(process_upload(uploaded))
        return processed

    def save(self):
        """Persist the processed images and return the created rows."""
        created = []
        has_primary = self.profile.photos.filter(is_primary=True).exists()
        next_order = self.profile.photos.count()

        for index, image in enumerate(self.cleaned_data["images"]):
            photo = ProfilePhoto.objects.create(
                profile=self.profile,
                image=image,
                sort_order=next_order + index,
                # The very first photo a member uploads becomes their main one.
                is_primary=(not has_primary and index == 0),
            )
            created.append(photo)
        return created
