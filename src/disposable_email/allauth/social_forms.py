from allauth.socialaccount import forms as social_forms

from .forms import DisposableEmailFormMixin


class SocialSignupForm(DisposableEmailFormMixin, social_forms.SignupForm):
    disposable_email_source = "social_signup"
