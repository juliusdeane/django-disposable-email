# Changes
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-09
### Added
- First release. It replaces the per-project copies used in ReciBRO, Taxiquo,
  Taska, EasyContract and Attentiometer.
- Blocking can be switched on and off with a setting, a database flag or a
  callable.
- The bundled list and a daily download are combined. The download is stored
  in the database and each process refreshes it lazily.
- Subdomains match their parent domain.
- Domains can be blocked or allowed by hand in the admin.
- allauth forms and mixin cover signup, add email and change email.
- A `pre_social_login` receiver blocks new social accounts, including
  auto-signup.
- Every blocked attempt is audited with the email masked, and an
  `email_blocked` signal is sent.
- Optional Celery task and a management command for the daily update.
- System check `disposable_email.W001` warns about allauth forms that are not
  wired.
- English and Spanish translations.
