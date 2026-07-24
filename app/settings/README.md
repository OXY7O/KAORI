# Settings Domain

## General Settings

`/settings/general` is a per-user workspace available to every authenticated KAORI account. It uses query-backed HTMX tabs so Time Zone, Regional Format, and System Information switch inside `#general-settings-page` without a full-page reload. Normal links remain the progressive-enhancement fallback.

Current tabs:

- `time-locale`: automatic browser timezone or a fixed IANA timezone.
- `regional-format`: regional locale, date format, and 12/24-hour time format.
- `system-information`: safe KAORI release identity and the capabilities shipped with the deployed version.

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
- System Information is visible to every authenticated user and therefore exposes only safe product metadata.
- Never expose credentials, secret environment-variable values, database URLs, provider endpoints, Redis details, Kubernetes credentials, or internal service addresses.
- The capability catalog describes features shipped in the release; it does not imply that every provider is configured or that every user has RBAC access.

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


## Data Lifecycle contract

`/settings/data-lifecycle` is the centralized cross-domain control plane for KAORI retention, archive storage, cleanup, verification, and lifecycle execution history. Activity Audit no longer owns a retention tab; it links to this workspace instead.

The page is deliberately domain-driven so growth does not create one menu per table:

- a compact domain selector exposes only registered adapters;
- the selected domain owns its policy detail and exact preview;
- Archive Storage is shared across domains;
- Execution History is filterable across all domains;
- future domains appear only after their lifecycle adapter and safety boundaries exist.

Policy changes and manual archive operations require `settings.manage_data_lifecycle`. Read-only users see disabled policy controls. Verified archive downloads require `settings.export_data_lifecycle`. Every change, request, completion, failure, and verification produces persistent KAORI operational feedback and Activity Audit evidence.

## Inventory Sync Configuration

`/settings/inventory-sync/` is the canonical control surface for Kubernetes Inventory synchronization. Access requires `settings.manage_integrations`; manual execution additionally requires `clusters.sync`.

The workspace exposes:

- automatic policy enable/disable and a configurable 5–1,440 minute interval;
- registered, eligible, and skipped cluster coverage;
- next scheduled run, latest dispatch, and active execution posture;
- a CSRF-protected **Sync All Inventory** action;
- the five most recent fleet `JobExecution` records;
- a direct link to the filtered Jobs & Executions registry.

Automatic synchronization is enabled by default at 60 minutes. Policy changes reset the next due time and are recorded as operational activity. The manual action always uses `enqueue_all_cluster_inventory_sync`, so it creates or attaches to the same canonical fleet `JobExecution` used by scheduled runs. No empty job is created when no cluster has an enabled canonical Kubernetes binding.

## Inventory Sync navigation contract

Inventory Sync is an operational scheduler and execution control surface. It is presented under **Platform Operations** beside **Jobs & Executions**, not under Settings. The implementation may remain in the settings package while it owns persisted policy configuration, but its user-facing navigation follows the operational job domain.

