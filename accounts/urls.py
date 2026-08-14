"""URLs for sign-up, verification and sign-in."""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("signup/check-your-email/", views.signup_done, name="signup_done"),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),
    path("resend-verification/", views.resend_verification, name="resend_verification"),
    path("login/", views.MemberLoginView.as_view(), name="login"),
    path("logout/", views.MemberLogoutView.as_view(), name="logout"),

    # Password reset uses Django's built-in views with this project's templates.
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="emails/password_reset.txt",
        subject_template_name="emails/password_reset_subject.txt",
        # Without this the templates would show the bare hostname as the brand.
        extra_email_context={"site_name": settings.SITE_NAME},
        success_url="/accounts/password-reset/sent/",
    ), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url="/accounts/password-reset/done/",
    ), name="password_reset_confirm"),
    path("password-reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
]
