"""Sign-up, email verification and sign-in views."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse

from .emails import send_verification_email
from .forms import EmailLoginForm, ResendVerificationForm, SignUpForm
from .tokens import read_verification_token

User = get_user_model()


def signup(request):
    """Create an account and send the verification email."""
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_verification_email(user)
            # Remember the address so the "check your inbox" page can show it
            # and offer a one-click resend.
            request.session["pending_verification_email"] = user.email
            return redirect("accounts:signup_done")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


def signup_done(request):
    """"Check your inbox" confirmation screen."""
    return render(request, "accounts/signup_done.html", {
        "email": request.session.get("pending_verification_email", ""),
        "expiry_hours": settings.EMAIL_VERIFICATION_TIMEOUT_HOURS,
    })


def verify_email(request, token):
    """Consume a verification link and sign the member in."""
    payload = read_verification_token(token)
    if not payload:
        return render(request, "accounts/verify_failed.html", {
            "reason": "This verification link is invalid or has expired.",
        }, status=400)

    user = User.objects.filter(pk=payload["uid"]).first()
    # The email is embedded in the token, so a link sent to an old address
    # stops working once the address changes.
    if user is None or user.email != payload["email"]:
        return render(request, "accounts/verify_failed.html", {
            "reason": "This verification link no longer matches an account.",
        }, status=400)

    if not user.is_active:
        return render(request, "accounts/verify_failed.html", {
            "reason": "This account has been deactivated. Please contact support.",
        }, status=403)

    already_verified = user.is_email_verified
    user.mark_email_verified()

    # Clicking the link proves control of the mailbox, so sign them straight
    # in — one less step between signing up and building a profile.
    login(request, user, backend="accounts.backends.EmailBackend")
    request.session.pop("pending_verification_email", None)

    if already_verified:
        messages.info(request, "Your email was already confirmed. Welcome back!")
    else:
        messages.success(request, "Email confirmed. Welcome — let's build your profile.")
    return redirect("profiles:edit")


def resend_verification(request):
    """Send a fresh verification link."""
    initial = {"email": request.session.get("pending_verification_email", "")}

    if request.method == "POST":
        form = ResendVerificationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user and not user.is_email_verified:
                send_verification_email(user)
                request.session["pending_verification_email"] = user.email
            # The response is identical whether or not the account exists, so
            # this page cannot be used to discover who is registered.
            messages.success(
                request,
                "If that address needs confirming, a new link is on its way.",
            )
            return redirect("accounts:signup_done")
    else:
        form = ResendVerificationForm(initial=initial)

    return render(request, "accounts/resend_verification.html", {"form": form})


class MemberLoginView(LoginView):
    """Sign in, blocking accounts that have not confirmed their email."""

    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not user.is_email_verified:
            self.request.session["pending_verification_email"] = user.email
            messages.warning(
                self.request,
                "Please confirm your email address before signing in. "
                f'<a href="{reverse("accounts:resend_verification")}">Send a new link</a>.',
                extra_tags="safe",
            )
            return redirect("accounts:login")
        return super().form_valid(form)


class MemberLogoutView(LogoutView):
    """Sign out and return to the login screen."""

    next_page = "accounts:login"
