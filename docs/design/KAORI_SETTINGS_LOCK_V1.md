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
- Compatibility Versions is matrix-first, not a six-column tiny-text wall: compact annual policy, concise reading guidance, grouped shared table columns, and a native Contract Ownership disclosure preserve policy, contract, qualified version, upstream lifecycle, KAORI support, and independent live readiness authorities. Use existing semantic surfaces and maintain keyboard-operable horizontal overflow at narrow widths.
- System Information remains a release-led, read-only reference without repeated nested cards: prominent runtime version, explicitly unknown missing build metadata, short curated themes (not runtime readiness), paired inline governance/privacy reference columns, and the native accessible capability accordion with defined hover/open surfaces.
- Account Profile and Authentication Activity remain full-width.
- Account Profile shows identity/link state rather than suggesting a live provider validation result; RBAC Role and Super Admin tier remain independent. Last Verified Sign-In records the canonical source and request IP with proxy caveat. Read-only identity and presentation settings retain a separate General Settings edit workflow.
- Recent Authentication Activity is event-first: a compact, divided inline summary scopes metrics to the latest five committed events, while the existing shared KAORI table remains primary. Conditional failure status, safe generic failure copy and proxy-dependent recorded IP evidence remain authoritative; the footer is a single neutral inline note. Sign-outs display Recorded rather than Sign-In Success without rewriting audit events. No separate mobile controller or decorative metric cards.
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
