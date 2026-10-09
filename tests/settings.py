SECRET_KEY = "tests"
DEBUG = False
USE_TZ = True
ALLOWED_HOSTS = ["*"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "disposable_email",
]
SITE_ID = 1
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]
ROOT_URLCONF = "tests.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_FORMS = {
    "signup": "disposable_email.allauth.forms.SignupForm",
    "add_email": "disposable_email.allauth.forms.AddEmailForm",
    "change_email": "disposable_email.allauth.forms.ChangeEmailForm",
}
SOCIALACCOUNT_FORMS = {"signup": "disposable_email.allauth.social_forms.SocialSignupForm"}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
LANGUAGE_CODE = "en"
DISPOSABLE_EMAIL = {"INCLUDE_PACKAGE_LIST": True}
