"""django-allauth integration.

- Forms (signup, add email, change email, social signup): use the ready forms
  in :mod:`disposable_email.allauth.forms` or add ``DisposableEmailFormMixin``
  to your own (first in the bases). A system check warns if one is missing.
- Social providers: nothing to wire. A ``pre_social_login`` receiver blocks
  NEW accounts with a disposable email (also with SOCIALACCOUNT_AUTO_SIGNUP,
  which skips the forms). Existing accounts keep logging in.

Not the adapter's ``clean_email``: allauth also calls it for password reset,
login by code and to read the provider's email (where errors are swallowed).
"""
