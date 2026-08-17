# KAORI Settings Lock v1

Status: **FINAL LOCKED**

## Scope

- General Settings
  - Time Zone
  - Regional Format
  - System Information
  - Compatibility Versions
- Account & Authentication
  - Account Profile & Access
  - Recent Authentication Activity
  - Credential Management

## Locked ownership

- General presentation preferences are per-user state; they never mutate canonical UTC data, schedules, Kubernetes, Prometheus, Alertmanager, or provider clocks.
- System Information and Compatibility Versions expose safe product/release metadata only and require `system.view`.
- Account credential changes are Local Database only; provider-managed credentials stay with the external identity provider.
- Successful local password replacement advances the authentication session generation, preserves the current browser, and revokes other sessions and remembered sign-ins.
- Authentication evidence remains audit-safe and never stores credential values.

## UI baseline

- KAORI Violet Hero and semantic tokens.
- General and Account use the same simple query-backed HTMX tab family.
- Time Zone and Regional Format keep their scope/data boundaries inline.
- Account Profile and Authentication Activity remain full-width.
- Credential Management uses natural-height action/context columns.
- Shared table/status/operational-feedback primitives own reusable semantics.
- No page-local raw palette, arbitrary text sizes/tracking, `font-extrabold`, inline styles, or inline DOM handlers.

## Retired surfaces

The following pre-lock side-context partials must not return:

- `settings/general/partials/_impact_information.html`
- `settings/account/partials/_profile_information.html`
- `settings/account/partials/_activity_information.html`

Permanent enforcement: `scripts/verify_settings_final_lock.py`.

## Settings Overview decision

- No dedicated Settings Overview is shipped while Settings owns only General and Account.
- `/settings/` remains the General Settings entry point.
- Add an Overview only after Settings has at least three independently owned workspaces or a real cross-settings posture requiring composition.

## Loading and operational feedback

- General and Account use the shared KAORI loading-bar component for HTMX tab switches and mutations.
- User-triggered Settings mutations return the canonical operational toast for success and failure; field errors remain inline.
- Background browser-timezone convergence stays silent.
- Notification/Activity progress surfaces use one shared notification-progress geometry rather than page-local track heights.
