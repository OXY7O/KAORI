# Settings Domain

## General Settings

`/settings/general` is a per-user workspace available to every authenticated KAORI account. It uses query-backed tabs so additional preference domains can be added without creating a long settings page or separate sidebar entries.

Current tabs:

- `time-locale`: automatic browser timezone or a fixed IANA timezone.
- `regional-format`: regional locale, date format, 12/24-hour time format.

The former standalone `/settings/time-locale` page has been removed. General Settings is the canonical location for these preferences.

## Time presentation contract

- Operational timestamps remain canonical UTC values in PostgreSQL and normalized stores.
- Every authenticated user owns a timezone and regional presentation preference.
- Automatic timezone mode synchronizes the browser IANA timezone through `settings.sync_browser_timezone` when the application opens.
- Server-rendered timestamps must use the Jinja filters `user_datetime`, `user_date`, or `user_time`; templates must not call `strftime()` directly.
- Relative ages such as `3h`, `12d`, and certificate days remaining are timezone independent.
- Explicit execution timezones remain authoritative for report schedules and external systems. A display preference must not rewrite schedule definitions, Kubernetes timestamps, Prometheus data, LDAP data, or OAuth provider clocks.

## Adding future General tabs

1. Add a stable tab key in `settings.general`.
2. Add a dedicated partial under `app/templates/settings/general/partials/`.
3. Store long-lived per-user preferences on the centralized `User` model in `app/models/`.
4. Add an Alembic migration and normalized validation helpers.
5. Explain the preference scope and operational boundary in the right-side information panel.
