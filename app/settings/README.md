# Settings Domain

## General Settings

`/settings/general` is a per-user workspace available to every authenticated KAORI account. It uses query-backed tabs so additional preference domains can be added without creating a long settings page or separate sidebar entries.

Current tabs:

- `time-locale`: automatic browser timezone or a fixed IANA timezone.
- `regional-format`: regional locale, date format, and 12/24-hour time format.
- `system-information`: safe KAORI release identity and the capabilities shipped with the deployed version.

The former standalone `/settings/time-locale` and `/settings/system-info` pages have been removed. General Settings is the canonical location for personal presentation preferences and safe release information.

## Save and notification contract

- Timezone and regional-format forms use HTMX and replace the General Settings workspace without a full page reload.
- Successful saves create a personal `user_preference` notification for the authenticated user.
- Preference saves do not use Flask flash messages or operational toast feedback.
- The response triggers `kaori:notifications-changed`, allowing the top Notification Center to refresh immediately.
- Normal form POST and redirect remain as progressive-enhancement fallback when HTMX is unavailable.

## Time presentation contract

- Operational timestamps remain canonical UTC values in PostgreSQL and normalized stores.
- Every authenticated user owns a timezone and regional presentation preference.
- Automatic timezone mode synchronizes the browser IANA timezone through `settings.sync_browser_timezone` when the application opens.
- Server-rendered timestamps must use the Jinja filters `user_datetime`, `user_date`, or `user_time`; templates must not call `strftime()` directly.
- Relative ages such as `3h`, `12d`, and certificate days remaining are timezone independent.
- Explicit execution timezones remain authoritative for report schedules and external systems. A display preference must not rewrite schedule definitions, Kubernetes timestamps, Prometheus data, LDAP data, or OAuth provider clocks.

## System Information contract

- `APP_VERSION` is the canonical deployed application version and should match the immutable image tag.
- `APP_BUILD_SHA` and `APP_BUILD_DATE` are optional immutable build metadata.
- System Information is visible to every authenticated user and therefore exposes only safe product metadata.
- Never expose credentials, secret environment-variable values, database URLs, provider endpoints, Redis details, Kubernetes credentials, or internal service addresses.
- The capability catalog describes features shipped in the release; it does not imply that every provider is configured or that every user has RBAC access.

## Adding future General tabs

1. Add a stable tab key in `settings.general`.
2. Add a dedicated partial under `app/templates/settings/general/partials/`.
3. Store long-lived per-user preferences on the centralized `User` model in `app/models/`.
4. Add an Alembic migration and normalized validation helpers when persistence changes.
5. Explain the preference scope and operational boundary in the right-side information panel.
