# Settings Domain

Settings v1 is final-locked. General Settings and Account & Authentication are release baselines; future changes require targeted regression evidence rather than presentation redesign.


## Settings Overview decision

Settings does **not** have a dedicated Overview page in the current release. The category owns only two top-level workspaces: General Settings and Account & Authentication. Adding an Overview now would introduce an extra navigation step without a distinct cross-settings posture or lifecycle. `/settings/` therefore remains the canonical entry to General Settings.

Create a Settings Overview only when at least three independently owned Settings workspaces exist, or when KAORI has a cross-settings posture that cannot be represented faithfully inside General or Account. Do not create an Overview merely to mirror the sidebar.

## Loading and action feedback contract

- General and Account tab switches use `components/workspace_tabs.html::render_query_tabs` as the shared query-backed HTMX tab authority and `components/loading_bar.html` for the workspace loading indicator.
- Settings save/password actions use the same indicator and shared primary action-button primitive.
- Successful preference and credential mutations use the shared operational toast.
- User-triggered save/password failures also return a canonical toast; field-level validation remains inline so the operator can correct the form without losing context.
- Automatic browser-timezone synchronization is intentionally silent because it is background preference convergence, not a user-triggered CRUD action.
- Settings must not introduce page-local loading-bar heights or page-local toast implementations.

## General Settings

`/settings/general` is a per-user workspace available to every authenticated KAORI account. It uses query-backed HTMX tabs so Time Zone, Regional Format, System Information, and Compatibility Versions switch inside `#general-settings-page` without a full-page reload. Normal links remain the progressive-enhancement fallback.

Current tabs:

- `time-locale`: automatic browser timezone or a fixed IANA timezone.
- `regional-format`: regional locale, date format, and 12/24-hour time format.
- `system-information`: safe KAORI release identity, curated release highlights, and the capabilities shipped with the deployed version.
- `compatibility-versions`: minimum compatible and recommended Kubernetes, Metrics Source provider, Alertmanager, and qualified MinIO baselines derived from canonical integration/provider compatibility contracts.

The former standalone `/settings/time-locale` and `/settings/system-info` pages have been removed. General Settings is the canonical location for personal presentation preferences and safe release information.

### General Settings presentation contract

- Keep the shared KAORI Violet page hero and use its right-side context panel for current preference or safe system metadata, not duplicate actions.
- Time Zone uses one full-width workspace: Selection Mode → Browser Detection / Manual Time Zone → inline Preference Scope & Boundary → Effective Time Zone → Save.
- Regional Format uses one full-width workspace: Format Controls → Current Presentation Preview → inline Preference Scope & Boundary → Effective Format → Save.
- Time Zone and Regional Format both embed presentation scope and operational boundaries inside their own workspace. Neither tab uses the shared right-side preference context. Preference UI must never imply that canonical UTC data, schedules, interface language, or external systems are mutated.
- System Information and Compatibility Versions are unified full-width read-only workspaces. Release governance, information boundaries, matrix-reading guidance, and compatibility policy live inline in the active workspace; do not restore dedicated right-side context boxes. Use shared semantic label primitives for read-only and validation posture.
- Keep long capability catalogs expandable and keep the supported-version matrix on the shared KAORI table primitive. Read-only reference tabs use one calm outer workspace, but must not become visually flat: System Information is release-led and Compatibility Versions is matrix-led, using accent bands, split evidence regions, dividers, and grouped lists instead of repeated equal-weight nested cards.

## Save and notification contract

- General tab navigation and the timezone/regional-format forms use HTMX and replace the General Settings workspace without a full-page reload.
- Successful saves persist a `user_preference` Activity Audit record for the authenticated user.
- Preference saves use the shared KAORI operational result toast and do not use Flask flash messages.
- Preference audit events use `AUDIT_ONLY`, so routine preference changes do not create unread Notification Center items.
- HTMX responses trigger `kaori:general-settings-saved`; `kaori:notifications-changed` is emitted only when a delivery policy actually creates a visible Notification Center item.
- Normal form POST and redirect remain as progressive-enhancement fallback when HTMX is unavailable.

## Time presentation contract

- Operational timestamps remain canonical UTC values in PostgreSQL and normalized stores.
- Every authenticated user owns a timezone and regional presentation preference.
- Automatic timezone mode synchronizes the browser IANA timezone through `settings.sync_browser_timezone` when the application opens.
- Server-rendered timestamps must use the Jinja filters `user_datetime`, `user_date`, or `user_time`; templates must not call `strftime()` directly.
- Relative ages such as `3h`, `12d`, and certificate days remaining are timezone independent.
- Explicit execution timezones remain authoritative for report schedules and external systems. A display preference must not rewrite schedule definitions, Kubernetes timestamps, Metrics Source data, LDAP data, or OAuth provider clocks.

## System Information contract

- `APP_VERSION` is the canonical deployed application version and should match the immutable image tag.
- `APP_BUILD_SHA` and `APP_BUILD_DATE` are optional immutable build metadata.
- `CHANGELOG.md` is the canonical operator-facing release-history source; System Information remains a safe runtime summary rather than a duplicate changelog.
- `docs/releases/KAORI_2_3_0.md` records the 2.3.0 release scope, publication boundary, and final verification command.
- Follow `docs/deployment/RELEASE_GOVERNANCE.md` for version bumps, tags, immutable image identity, and release approval.
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
5. Explain the preference scope and operational boundary in the active workspace; use a side context panel only when it improves the information hierarchy.

## Account & Authentication contract

`/settings/account` is organized into `profile`, `activity`, and `credentials` query-backed HTMX tabs. Tab navigation replaces `#account-authentication-page` without a full-page reload, updates the browser URL, and preserves normal-link fallback.

### Account & Authentication presentation contract

- Use the same simple tab contract as General Settings; do not reintroduce page-local tab runtimes or count/status badges into the tab labels.
- Keep the Hero focused on a compact posture summary: Account Posture, Authentication Evidence, and Credential Posture.
- Profile stays full-width and read-only. Identity ownership, role/lifecycle posture, personal presentation, Last Verified Sign-In, and the access boundary belong in the active profile workspace.
- Authentication Activity stays full-width and uses the shared KAORI table and status-label primitives with an inline Authentication Evidence boundary. Avoid hand-built status badges.
- Credential Management keeps the action workspace on the left and one security context panel on the right at wide breakpoints; columns remain natural-height and top-aligned.
- Do not restore the retired `_profile_information.html` or `_activity_information.html` side-context partials. Their canonical evidence now lives inline in the active Profile and Authentication Activity workspaces.

Local Database password changes use HTMX and replace `#account-authentication-page` without a full-page reload. The canonical Local Database password policy is a unique passphrase of at least 12 characters (maximum 1024), with known default values rejected. A successful password change:

- creates a personal `account_security` notification for the authenticated user;
- triggers `kaori:notifications-changed` only when the persistent account-security notification is visible;
- returns the shared KAORI Violet operational result toast through an out-of-band HTMX swap;
- does not render a duplicate inline success banner after the toast is emitted;
- excludes current and new password values from notification and audit metadata;
- advances `User.auth_session_version`, preserves the current browser session on the new generation, and revokes other authenticated sessions plus remembered sign-ins on their next request;
- clears the current browser's remember cookie so persistence must be re-established with the replacement password;
- keeps profile, role, lifecycle state, Super Admin tier, and external identity links unchanged.

Incorrect-current-password and current-password-reuse attempts are persisted as `AUDIT_ONLY` `account_security` failures without creating Notification Center unread items.

Normal POST and redirect remain available only as progressive-enhancement fallback when HTMX is unavailable.


## Data Lifecycle compatibility boundary

Data Lifecycle is no longer owned by Settings. The canonical operator workspace is **Platform Operations → Data Lifecycle** at `/platform-operations/data-lifecycle/`. `/settings/data-lifecycle/` remains redirect-only compatibility for existing bookmarks and stale links; no lifecycle mutation or presentation logic may return to `app/settings/data_lifecycle_compat.py`.

## Background Job Boundary

Automatic schedules and manual background-job controls are owned by `app.platform_operations.jobs` under **Platform Operations → Jobs & Executions → Job Configuration**. Settings must not introduce job-specific scheduler pages or direct Celery dispatch routes.

## Access ownership boundary

Roles & Access and Permission Catalog are owned exclusively by `app/access/` at `/access/roles/` and `/access/permissions/`. Settings contains no role/permission routes, templates, forms, redirect shims, or compatibility wrappers. Historical `/settings/roles*` and `/settings/permissions` URLs are intentionally retired; stale bookmarks must use the canonical Access routes.
