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
- Shared Settings query-backed tablists retain horizontal scrolling for narrow viewports but must have no vertical overflow. Avoid a negative bottom margin on selected tabs: combined with `overflow-x-auto`, a 1px excess height can expose a phantom vertical scrollbar. Active tab surface, focus, ARIA and HTMX behavior remain unchanged.
- Time Zone and Regional Format keep their scope/data boundaries inline.
- Compatibility Versions UAT-1 policy disclosure refinement (#2242): keep the native accessible two-column Reading the Matrix / Policy Boundary reference, with four semantically matched equal-height desktop rows and aligned divider rules; use concise nontruncated descriptions, and natural stacked wrapping on mobile. This changes presentation only; annual lifecycle and provider qualification doctrine remain unchanged.
- Compatibility Versions uses the existing Settings GET + HTMX query-backed Registry + Detail pattern rather than a dense compatibility table: compact annual policy; server-side product search/filter and 5-item pagination; server-side 5-row qualification pagination; selected detail with stable contract, versions, upstream lifecycle, KAORI support and independent live-readiness authority; and a native Policy Boundary disclosure. Keep `system.view`, full GET fallback, query-state URLs, semantic surfaces and source-controlled provider definition authority. No live provider lookup is implied by the registry. The filter form uses debounced HTMX search and immediate support-select change without a visible Apply button, updating only the results partial (stable keyboard focus) with normal GET/noscript fallback. The registry list is capped at 33rem, allowing the default five products to remain visible before overflow; pagination stays outside that scroll region. Active selection uses one violet edge, while nonselected hover remains neutral. Qualification Detail uses a single readable metadata grid, separate KAORI/upstream semantics, a plain readiness boundary and compact version rows with no redundant nested cards; the native policy disclosure remains unchanged.
- General Settings UAT-1 desktop copy refinement (#2241): concise explanatory text in Time Zone scope, release themes, Information Boundary, capabilities, and Compatibility Versions reduces avoidable wrapping without truncation/nowrap. Small screens may wrap naturally. Provider lifecycle policy, compatibility bands, credentials, canonical UTC storage, and execution semantics remain authoritative and unchanged.
- System Information remains a release-led, read-only reference without repeated nested cards: prominent runtime version, explicitly unknown missing build metadata, short curated themes (not runtime readiness), paired inline governance/privacy reference columns, and the native accessible capability accordion with defined hover/open surfaces.
- General Settings Time Zone, Regional Format, System Information, and Integration Compatibility headings each use exactly one canonical title-adjacent `components/info_tip.html` Violet `Guide` (`variant='guide'`), with shared hover, focus, touch and viewport-clamped presentation. Guide content explains account presentation, read-only release boundaries, or source-qualified compatibility; do not introduce page-local tooltips or hide required security/error guidance.
- The System Information Release Focus and capability labels use concise, source-owned descriptions to fit normal desktop rows without truncation or forced nowrap: shared job/delivery/analytics evidence, TLS inventory/governance/bulk rotation/worker sync, and compact analytics tabs retaining canonical navigation. Narrow viewports may wrap naturally; release scope, provider authority, and capability details remain unchanged.
- Account Profile and Authentication Activity remain full-width.
- Account Profile shows identity/link state rather than suggesting a live provider validation result; RBAC Role and Super Admin tier remain independent. Last Verified Sign-In records the canonical source and request IP with proxy caveat. Read-only identity and presentation settings retain a separate General Settings edit workflow.
- Recent Authentication Activity is event-first: a compact, divided inline summary scopes metrics to the latest five committed events, while the existing shared KAORI table remains primary. Conditional failure status, safe generic failure copy and proxy-dependent recorded IP evidence remain authoritative; the footer is a single neutral inline note. Sign-outs display Recorded rather than Sign-In Success without rewriting audit events. No separate mobile controller or decorative metric cards. Recent Authentication Activity table order is Event → Source → Context → Result. Text-heavy Context (including browser/device evidence) stays left aligned; the trailing compact Result header and badge use the shared right-aligned cell variant. This supersedes the visually unbalanced Context-last arrangement without changing committed evidence or status semantics.
- Credential Management uses natural-height action/context columns for both Local Database and external identities. Local accounts retain password form, policy, session rotation and audit semantics; LDAP/SSO use the same Violet guidance hierarchy without local edit/reset controls or invented provider recovery links. Show credential owner only in security context, preserve KAORI-owned role/lifecycle checks, and do not imply KAORI observes provider password resets; its authentication audit is limited to locally observed events.
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

- **Superseding human UAT-1 / #2225 (2026-10-17): no visible loading/progress bar anywhere in Settings General or Account & Authentication, including content cards and tab boundaries.** The earlier #2237 content-card relocation and #1151 indicator placement are superseded for visual progress feedback. Preserve HTMX indicator IDs as nonvisual accessible `role=status` regions owned by the Settings page, plus existing submit-button pending states, operational toasts, inline validation, query-backed `hx-get`/`hx-target`/`hx-sync`/`hx-push-url`, and real href fallback. Do not revive `components/loading_bar.html::render` in any General/Account tab.
- User-triggered Settings mutations return the canonical operational toast for success and failure; field errors remain inline.
- Background browser-timezone convergence stays silent.
- Explicit **Detect Again** presents the canonical Operational Toast for detected/unchanged or failure outcomes, without persisting the local browser observation, producing an Activity Audit event, or creating a Notification Deck item. It does not replace **Save Time Zone**.
- Notification/Activity progress surfaces use one shared notification-progress geometry rather than page-local track heights.

## Planned MFA self-service placement (authority #562, AUTH-UI-01 / #3138)

After tested TOTP enrollment and verified factor persistence (#3134), a bounded Settings → Account & Authentication self-service tab will own MFA enrollment, recovery codes and state. It must reuse the current query-backed HTMX tabs and existing Settings Final Lock; it must not expose an admin-wide security policy or duplicate Identity Provider management. This note is future placement authority, **not** a claim that factor enrollment currently exists or is active.


## Superseding MFA self-service delivery (#3134)

Settings → Account & Authentication now includes an MFA tab for TOTP manual
setup, confirmation, one-time recovery-code display and authenticated
recovery regeneration. This uses the existing query-backed Settings tab
family and does not own global MFA or Bot Protection administration.
Factor security remains governed by the Access MFA policy and the
restricted post-primary challenge; UI availability does not imply that
every user's MFA policy is enabled. Do not disclose QR/manual secrets or
recovery codes in Activity Audit. Full browser acceptance pending.


## Personal MFA enrollment workspace visual refinement (#3228)

Settings → Account & Authentication → Multi-Factor Authentication reuses the
approved **Account Profile & Access** full-width header/status presentation and
**Credential Management** natural-height action/context composition. It does
not introduce a separate Settings page, another sidebar capability, a custom
form controller, or a new visual component family.

- A single **icon + title + canonical Info Tip Guide + state indicator** owns
  the MFA header. The three compact posture cards show the committed
  individual factor state, the Access-owned MFA policy, and actual remaining
  recovery-code count. Do not confuse `Factor Enrolled` with MFA policy
  enforcement or count all enrolled users.
- On unenrolled/pending accounts, the **left 7/12 action column** contains
  Step 01 (generate manual setup key) and Step 02 (verify six-digit TOTP); the
  **right 5/12 context column** describes the same three-step onboarding and
  primary-provider/KAORI authority boundary. On enrolled accounts the same
  action/context pattern hosts recovery-code regeneration and its warning.
  Panels naturally stack on narrow screens.
- Password controls are limited to `max-w-md`, enrollment TOTP confirmation
  to `max-w-[15rem]`, and recovery-code verification to `max-w-sm` with
  `w-full` inside each bounded container. Do not stretch six-digit controls
  to full desktop width, force nowrap, or invent a QR generator.
- The existing self-service server routes and form values (`begin`,
  `confirm`, `regenerate`, `current_password`, `verification_code`, CSRF)
  retain ownership; required `login_fresh()`, local-password and external
  provider guardrails are unchanged. Setup key and one-use recovery-code
  responses remain transient and marked `Cache-Control: no-store`.
- Use KAORI Violet semantic surfaces, shared `table_label` and title Guide,
  real Lucide icons with accessible text, visible validation feedback, light/
  dark themes and Settings Final Lock's **nonvisual** HTMX loading status.
  Do not introduce visible loading/progress bars.

Acceptance is scoped automated contract + Settings Final Lock, djlint, then
human screenshot UAT for not-enrolled/pending/enrolled/recovery views in
desktop/mobile and both themes. Human factor/challenge enrollment acceptance
remains separate; no migration or authentication backend change for this
redesign.


## Approved personal MFA visual mockup implementation (#3228)

The operator reviewed and approved the second MFA Settings mockup on 2026-10-25. It supersedes the previous flat enrollment layout while retaining the approved sibling Account components and Settings Final Lock. The design keeps one clear page title and canonical Guide, adds **decorative smartphone/shield icon geometry** to a Violet-soft header (not a functional QR code), and presents three icon-led state cards for actual factor enrollment, committed Access policy and recovery-code availability. Do not fabricate provider health, OTP coverage or a QR setup workflow.

Enrollment uses the established **7/5 natural-height Account action/context grid** with a numbered Step 01 (Generate Setup Key) and Step 02 (Verify Your Authenticator) on the left. The guide on the right now stretches alongside both steps rather than ending midway and leaving blank canvas. The six-digit confirmation stays **one semantic `verification_code` input**, with numeric keypad/autocomplete/pattern/length contracts and extra visual letterspacing instead of six new inputs or custom JavaScript. Existing max-width password/recovery controls and compact OTP control remain ergonomic. The footer is a subtle contextual **Security Information** surface, not a new global alert/toast.

The existing enrolled recovery-regeneration UI, sensitive one-time secret response, `Cache-Control: no-store`, CSRF, local-password/fresh sign-in checks, HTMX tabs and approved Settings loading behavior remain authoritative. Only account MFA presentation and focused visual contracts change; TOTP cryptographic representation hardening has its own security issue #3237. Accept by exact-SHA djlint/Ruff/pytest, desktop/mobile light/dark screenshots, keyboard/contrast review and human confirmation before any official admission.
