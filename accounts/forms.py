"""Sign-up and sign-in forms."""

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


class SignUpForm(forms.ModelForm):
    """Create an account from an email address and a password."""

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password",
                                          "placeholder": "At least 8 characters"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password",
                                          "placeholder": "Repeat your password"}),
    )
    accept_terms = forms.BooleanField(
        label="I confirm I am 18 or older and accept the terms of use.",
        required=True,
    )

    class Meta:
        model = User
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email",
                                             "placeholder": "you@example.com"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("The two passwords do not match.")
        # Run Django's validators (length, common passwords, all-numeric).
        password_validation.validate_password(p2, self.instance)
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class EmailLoginForm(AuthenticationForm):
    """Login form labelled for email, with clearer error messages."""

    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email",
                                       "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password",
                                          "placeholder": "Your password"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "That email and password do not match an account.",
        "inactive": "This account has been deactivated. Please contact support.",
    }

    def confirm_login_allowed(self, user):
        # `is_active` covers the admin's deactivate switch; the unverified case
        # is handled in the view so we can offer a "resend link" action.
        super().confirm_login_allowed(user)


class ResendVerificationForm(forms.Form):
    """Ask for a fresh verification link."""

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email",
                                       "placeholder": "you@example.com"}),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
