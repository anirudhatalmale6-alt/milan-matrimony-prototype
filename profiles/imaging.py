"""Photo normalisation.

Phones produce 4–12 MB photos that are far larger than any page needs, and
they carry EXIF metadata (including GPS coordinates). Every upload is
therefore re-encoded: rotated upright, resized, stripped of metadata and
saved as a progressive JPEG.
"""

import io

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def process_upload(uploaded_file) -> InMemoryUploadedFile:
    """Validate and re-encode one uploaded image.

    Raises ValidationError with a message meant for the member.
    """
    max_bytes = settings.MAX_PHOTO_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(
            f"“{uploaded_file.name}” is larger than {settings.MAX_PHOTO_SIZE_MB} MB."
        )

    try:
        image = Image.open(uploaded_file)
        # verify() catches truncated/corrupt files but leaves the object
        # unusable, so the file has to be reopened afterwards.
        image.verify()
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
    except (UnidentifiedImageError, OSError):
        raise ValidationError(f"“{uploaded_file.name}” is not a readable image file.")

    if image.format not in ALLOWED_FORMATS:
        raise ValidationError(
            f"“{uploaded_file.name}” is a {image.format} file. Use JPG, PNG or WebP."
        )

    # Apply the EXIF orientation flag, then drop the metadata with it.
    image = ImageOps.exif_transpose(image)

    # Flatten transparency onto white so PNG/WebP cut-outs do not turn black
    # when saved as JPEG.
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        backdrop = Image.new("RGB", image.size, (255, 255, 255))
        backdrop.paste(image, mask=image.split()[-1])
        image = backdrop
    elif image.mode != "RGB":
        image = image.convert("RGB")

    limit = settings.PHOTO_MAX_DIMENSION
    if max(image.size) > limit:
        image.thumbnail((limit, limit), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=settings.PHOTO_JPEG_QUALITY,
               optimize=True, progressive=True)
    buffer.seek(0)

    name = uploaded_file.name.rsplit(".", 1)[0][:60] or "photo"
    return InMemoryUploadedFile(
        buffer, field_name="image", name=f"{name}.jpg",
        content_type="image/jpeg", size=buffer.getbuffer().nbytes, charset=None,
    )
