# Settings Domain

## General Settings

`/settings/general` is a per-user workspace available to every authenticated KAORI account. It uses query-backed HTMX tabs so Time Zone, Regional Format, System Information, and Compatibility Versions switch inside `#general-settings-page` without a full-page reload. Normal links remain the progressive-enhancement fallback.

Current tabs:

- `time-locale`: automatic browser timezone or a fixed IANA timezone.
- `regional-format`: regional locale, date format, and 12/24-hour time format.
- `system-information`: safe KAORI release identity, release 2.1.0 highlights, and the capabilities shipped with the deployed version.
- `compatibility-versions`: minimum compatible and recommended Kubernetes, Prometheus, Alertmanager, and Thanos Query baselines derived from the canonical integration compatibility policy.

The former standalone `/settings/time-locale` and `/settings/system-info` pages have been removed. General Settings is the canonical location for personal presentation preferences and safe release information.

## Save and notification contract

- General tab navigation and the timezone/regional-format forms use HTMX and replace the General Settings workspace without a full-page reload.
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
- System Information and Compatibility Versions require `system.view` and expose only safe product metadata.
- Never expose credentials, secret environment-variable values, database URLs, provider endpoints, Redis details, Kubernetes credentials, or internal service addresses.
- The capability catalog describes features shipped in the release; it does not imply that every provider is configured or that every user has RBAC access.
- Compatibility Versions distinguishes the oldest profile-backed runtime from the recommended baseline for new deployments. Version matching never replaces live API, metric, label, query-evidence, or RBAC validation.
- Compatibility labels describe KAORI application policy and must not be presented as the upstream product support or end-of-life calendar.

## Adding future General tabs

1. Add a stable tab key in `settings.general`.
2. Add a dedicated partial under `app/templates/settings/general/partials/`.
3. Store long-lived per-user preferences on the centralized `User` model in `app/models/`.
4. Add an Alembic migration and normalized validation helpers when persistence changes.
5. Explain the preference scope and operational boundary in the right-side information panel.

## Account & Authentication contract

`/settings/account` is organized into `profile`, `activity`, and `credentials` query-backed HTMX tabs. Tab navigation replaces `#account-authentication-page` without a full-page reload, updates the browser URL, and preserves normal-link fallback. Information panels in the Activity and Credential tabs use native `<details>` elements and remain closed by default so the workspace can grow without creating a permanently long page.

Local Database password changes use HTMX and replace `#account-authentication-page` without a full-page reload. A successful password change:

- creates a personal `account_security` notification for the authenticated user;
- triggers `kaori:notifications-changed` so the top Notification Center refreshes immediately;
- returns the shared KAORI Violet operational result toast through an out-of-band HTMX swap;
- does not render a duplicate inline success banner after the toast is emitted;
- excludes current and new password values from notification and audit metadata;
- keeps profile, role, lifecycle state, Super Admin tier, and external identity links unchanged.

Normal POST and redirect remain available only as progressive-enhancement fallback when HTMX is unavailable.


## Data Lifecycle compatibility boundary

Data Lifecycle is no longer owned by Settings. The canonical operator workspace is **Platform Operations → Data Lifecycle** at `/platform-operations/data-lifecycle/`. `/settings/data-lifecycle/` remains redirect-only compatibility for existing bookmarks and stale links; no lifecycle mutation or presentation logic may return to `app/settings/data_lifecycle_compat.py`.

## Background Job Boundary

Automatic schedules and manual background-job controls are owned by `app.jobs` under **Platform Operations → Jobs & Executions → Job Configuration**. Settings must not introduce job-specific scheduler pages or direct Celery dispatch routes.

## Access ownership boundary

Roles & Access and Permission Catalog are owned exclusively by `app/access/` at `/access/roles/` and `/access/permissions/`. Settings contains no role/permission routes, templates, forms, redirect shims, or compatibility wrappers. Historical `/settings/roles*` and `/settings/permissions` URLs are intentionally retired; stale bookmarks must use the canonical Access routes.
