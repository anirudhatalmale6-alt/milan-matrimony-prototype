"""
Django settings for the Milan matrimony prototype.

Every value that changes between machines (secret key, database, SMTP, brand
name) is read from the environment so the same code runs locally and in
production without edits. See `.env.example` for the full list.
"""

from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load a local .env file if one exists. In production the platform normally
# injects real environment variables instead, which take precedence.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean-ish environment variable ("1", "true", "yes")."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable into a clean list."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DEBUG", True)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"] if DEBUG else []

# Hosts allowed to POST forms (Django 4+ requires the scheme).
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Branding. The client can rename the whole site from a single env var.
SITE_NAME = os.getenv("SITE_NAME", "Milan")
SITE_TAGLINE = os.getenv("SITE_TAGLINE", "Where two journeys become one")
# Absolute base URL used to build links inside verification emails.
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://127.0.0.1:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "accounts",
    "profiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves compressed static files without needing nginx in front.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Closes the site to guests: everything outside the public allow-list
    # redirects to the login page.
    "accounts.middleware.LoginRequiredMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Makes SITE_NAME / SITE_TAGLINE available in every template.
                "config.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
# Defaults to SQLite so the project runs immediately after `pip install`.
# Set DATABASE_URL (e.g. postgres://user:pass@host:5432/db) for PostgreSQL.

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = ["accounts.backends.EmailBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "profiles:browse"
LOGOUT_REDIRECT_URL = "accounts:login"

# URL names reachable without being signed in. Everything else is gated by
# LoginRequiredMiddleware.
PUBLIC_URL_NAMES = {
    "accounts:login",
    "accounts:signup",
    "accounts:signup_done",
    "accounts:verify_email",
    "accounts:resend_verification",
    "accounts:password_reset",
    "accounts:password_reset_done",
    "accounts:password_reset_confirm",
    "accounts:password_reset_complete",
}

# Hours a verification link stays valid.
EMAIL_VERIFICATION_TIMEOUT_HOURS = int(os.getenv("EMAIL_VERIFICATION_TIMEOUT_HOURS", "48"))

# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
# Without EMAIL_HOST configured, mail is printed to the console. That keeps
# local development and CI runs from needing real SMTP credentials.

if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"{SITE_NAME} <no-reply@localhost>")

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static & media files
# --------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # The hashed-filename manifest only exists after `collectstatic`, so it
        # is used for real deployments and skipped during development/tests.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if os.getenv("USE_STATIC_MANIFEST", "auto") == "1"
        or (os.getenv("USE_STATIC_MANIFEST", "auto") == "auto" and not DEBUG
            and (BASE_DIR / "staticfiles" / "staticfiles.json").exists())
        else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# --------------------------------------------------------------------------
# Uploads
# --------------------------------------------------------------------------

# Per-photo limit before compression, and how many photos one profile may hold.
MAX_PHOTO_SIZE_MB = int(os.getenv("MAX_PHOTO_SIZE_MB", "8"))
MAX_PHOTOS_PER_PROFILE = int(os.getenv("MAX_PHOTOS_PER_PROFILE", "10"))
# Longest edge (px) a stored photo is resized down to, and its JPEG quality.
PHOTO_MAX_DIMENSION = int(os.getenv("PHOTO_MAX_DIMENSION", "1600"))
PHOTO_JPEG_QUALITY = int(os.getenv("PHOTO_JPEG_QUALITY", "85"))
# Allow the request body to carry a full batch of photos.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_PHOTO_SIZE_MB * MAX_PHOTOS_PER_PROFILE * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = MAX_PHOTOS_PER_PROFILE + 10

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Security (applied when DEBUG is off)
# --------------------------------------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"
