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
- General and Account use the same simple query-backed HTMX tab family, owned by `components/workspace_tabs.html::render_query_tabs`.
- The shared query-backed tab strip uses `bg-surface-hover` behind a selected `bg-surface-card` tab in both light/dark modes; this reuses the existing semantic surface palette, not a new Settings tab style.
- Time Zone and Regional Format keep their scope/data boundaries inline.
- System Information uses the existing release-led, read-only workspace: prominent runtime version, explicit missing build provenance, curated product themes (not runtime readiness), semantic contrast between governance/boundary panels, and a native accessible capability accordion with defined hover/open surfaces.
- Account Profile and Authentication Activity remain full-width.
- Account Profile shows identity/link state rather than suggesting a live provider validation result; RBAC Role and Super Admin tier remain independent. Last Verified Sign-In records the canonical source and request IP with proxy caveat. Read-only identity and presentation settings retain a separate General Settings edit workflow.
- Recent Authentication Activity scopes metric counts to the latest five committed events, renders evidence-aware failure badges, safely summarizes failed sign-ins without leaking internal audit reasons, and labels recorded request IP as proxy-dependent. Its snapshot uses existing Violet-soft/semantic contrast, elevated metrics and a compact inline evidence note; sign-out audit records display as Recorded rather than Sign-In Success.
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
- Explicit **Detect Again** presents the canonical Operational Toast for detected/unchanged or failure outcomes, without persisting the local browser observation, producing an Activity Audit event, or creating a Notification Deck item. It does not replace **Save Time Zone**.
- Notification/Activity progress surfaces use one shared notification-progress geometry rather than page-local track heights.
