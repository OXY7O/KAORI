# KAORI — Integration Provider Selection UAT

## Authority and standard

Issue #3106 establishes the approved provider-first registration workflow for
the six Integration domains: Orchestration, Observability, Storage, Registry,
Secrets Management, and Source Control.

**Domain → Integration Type → Choose Provider → Provider-Owned Register Connection.**

The Integration Provider Matrix remains authoritative for available versus
unavailable providers. Existing provider routes and Flask-WTF forms retain
credential, compatibility, CSRF, permission, and validation authority. The
canonical Metrics Source selector is preserved, including Prometheus and
Thanos Query. No invented registrations for matrix entries that are not
available.

## Registration entrypoints

| Integration type | Available provider | Provider-owned registration endpoint |
| --- | --- | --- |
| Container Orchestrator | Kubernetes | `cluster.add_cluster` |
| Metrics Source | Prometheus / Thanos Query | Existing `integrations.select_metrics_source_provider` → `integrations.register_metrics_source` |
| Alert Source | Alertmanager | `alertmanager.new_instance` |
| Object Storage | MinIO | `minio.new_instance` |
| Registry | Harbor | `harbor.new_instance` |
| Secrets & PKI | HashiCorp Vault | `vault.new_instance` |
| Source Control | GitHub | `github_source.new_connection` |

File/Block Storage and other matrix entries remain visible as unavailable,
without actionable registration. Notification Channels retain the established
channel-type chooser and channel-specific form workflow rather than being
incorrectly modeled as infrastructure-provider matrix entries.

**Current read-first navigation (#3207; supersedes the old Open CTA):**
The shared domain workspace **Open [integration]** action navigates directly
to the provider-owned `IntegrationModule.workspace_endpoint` and its
Coverage/Connection Registry, including empty states before registration.
A separate **Add Connection** action invokes the reusable provider selector
`integrations.choose_integration_provider`. Registration actions in the
provider frontpages likewise keep their existing provider-first selector
journey, not a shortcut directly to credentials. The sidebar remains
capability-first; no product-specific routing branches are introduced.
Provider overview/registry, saved connections, bindings, permission and
operational semantics remain independent and unchanged.

All canonical provider landing pages also reuse
`components/integration_workspace_tabs.html`, whose shared header now
renders **Integration Workspace** and **Review committed coverage and
registered provider connections.** above the existing two-tab surface.
Historical navigation checks below that say **Open → Choose Provider**
describe earlier candidates and must now be executed via **Add Connection**.

## Metrics Source provider chooser visual refinement (#3112)

The existing `/integrations/observability/metrics-sources/new` selector
retains Prometheus and Thanos Query provider-defined registration URLs.
Its Hero context helper is now **"Adapters own validation and runtime."**
to fit a single line on the reviewed desktop reference without forced
nowrap or truncation at mobile breakpoints.

Provider cards use the same Violet border/hover treatment as the shared
cross-domain selector. **Adapter**, **Query Language**, and the main
**Guide** use the current anchored KAORI `info_tip.render` macro for
pointer, keyboard and touch. The longer explanation is in the popovers
rather than crowding the visible hero. Shared responsive columns and
the existing primary registration button are preserved.

**Human visual UAT / executable QA pending:** review at 1440×900 and
a narrow viewport in light/dark mode. Check the context helper is one
line on desktop, hover or focus reveals correct guidance, card focus
and registration actions work, and both existing Prometheus / Thanos
provider forms open without altering credentials.

```bash
python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_metrics_source_routing_audit_20260817_contract.py
djlint --check \
  app/templates/integrations/observability/metrics_source/provider_selector.html
```

## Functional Dev Container UAT

1. For each of the six Integration domain pages, use **Open**.
   Verify it lands directly on the provider-owned Integration Overview with
   Coverage/Connection Registry, without passing through Add Connection.
   Confirm the shared Integration Workspace title and short description
   appear above the provider tabs, even with zero registered connections.
2. Use the separate **Add Connection** action for each integration type.
   Verify the selector lists matrix providers, makes only available choices
   actionable, and does not skip the provider chooser. In Observability,
   check both Metrics Source (Prometheus, Thanos Query) and Alert Source
   (Alertmanager); each available provider opens its existing form.
3. For Storage choose MinIO; for Registry choose Harbor; for Orchestration
   choose Kubernetes; for Secrets Management choose Vault; for Source Control
   choose GitHub. Verify **Back to Integrations** and the provider selection
   state, including narrow/mobile viewport and light/dark.
4. Confirm provider frontpage **Register Connection** actions enter the
   same selector before opening provider-specific configuration.
5. Check hover/click/focus on standard KAORI guide/info tips, the Hero
   single-line helper on desktop, button and card focus styling, and correct
   non-actionable unavailable cards.
6. Do not provide secrets during initial navigation UAT. Run connection
   registration, Test Connection, Full Validation, and committed evidence
   checks under each provider's existing functional runbook.

## Checks

```bash
python -m ruff check app/integrations/routes.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py

python -m ruff format --check app/integrations/routes.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py

python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py

djlint --check \
  app/templates/integrations/provider_selector.html \
  app/templates/integrations/partials/_domain_workspace.html
```

**Evidence state:** implementation/source review only; executable Dev
Container results and browser Human Acceptance are **pending**. No official
CI/CD/Developer Check/Full Admission, promotion to `kaori/staging` or main,
deployment, tag, or release until explicitly authorized.

**Historical UAT context:** Sections #3119/#3126 below preserve the
original operator observations. Where they prescribe **Open → Choose
Provider**, use **Add Connection → Choose Provider** on the current
holding branch (#3207). Do not revert direct workspace entry merely to
satisfy a historical screenshot.

## 2026-10-25 — #3119 sidebar and chooser visual follow-up

Operator visual UAT at 1440×900 found that dynamic `/integrations/providers/source_control` highlighted **Overview** instead of **Source Control**, and the single GitHub tile left an unused half-column. Corrected using the canonical navigation owner and matrix-derived domain identity, while the shared six-domain selector renders one provider as a compact full-width row and multiple providers in a responsive grid. Provider availability, credential handling, registration routes, RBAC, CSRF, evidence and validation behavior are unchanged.

**Exact-candidate Dev Container retest:**

1. Source Control → Open Source Control: sidebar highlights Source Control and breadcrumb shows Integrations → Source Control → Choose Provider. Verify the other provider chooser types highlight the owning capability, including both Observability types.
2. Single-provider GitHub selection uses full row width with one Register GitHub CTA. With multiple/disabled providers verify balanced cards, clear status and no actionable registration for unavailable entries.
3. Hover/click/keyboard-focus Provider Registration, Adapter and Protocol info tips. Inspect 1440×900 and 390×844, light and dark, without clipping or sideways overflow.
4. Register GitHub opens the existing GitHub App form; Test Connection and Register Connection buttons are present and admission-gated. No credentials are needed for this navigation/visual UAT.
5. Run Ruff, Ruff Format, djLint, selected pytest, `verify_sidebar_navigation_standard.py`, `verify_integration_domain_navigation.py`, `verify_ui_style.py`, `verify_ui_reuse.py` and existing browser/Visual QA as available.

**Earlier operator evidence:** 33 passed, 1 failed (line-sensitive GitHub form button action test); Integration Domain Navigation verifier PASS. The action test is now whitespace-tolerant without changing security enforcement. Executable verification on the new candidate and Human Acceptance remain **PENDING** until actual Dev Container evidence is recorded. Official admission remains HOLD.

## 2026-10-25 — #3126 Source Control planned provider card UAT

**Authority:** #3126 (follow-up to #3106 and navigation refinement #3119).
Human screenshot and feedback on the preceding UAT candidate confirmed the
Source Control sidebar is active and the focused tests were **52 PASS**,
with both navigation verifiers PASS. The wide single-provider row remained
visually rejected; field-level hover behavior was not accepted.

**Candidate behavior:** Provider Matrix now contains **GitHub (available)**,
**GitLab (planned)**, **Bitbucket (planned)**. Only GitHub has an admitted
registration endpoint. Planned provider metadata explicitly says adapter
**Not implemented** and protocol **Not defined**, rather than implying a
working implementation. The reusable selector displays equal-height cards,
available-first provider order, a real disabled button for planned providers
and a single title-level canonical `Guide` Info Tip. Adapter and Protocol
appear as plain compact labels, without repeated question-mark icons. The
shared `components/info_tip.html` plus `app/static/js/info_tips.js` controller
continues to own Guide hover/focus/touch behavior; no custom tooltip CSS/JS
or new provider implementation is introduced.

**Test steps — navigation-only, no credentials:**

1. Update to the exact holding SHA and restart Flask. Open
   **Integrations → Source Control → Open Source Control**.
   Expect Source Control active, breadcrumb ending **Choose Provider**.
2. At **1440×900** in **light** and **dark** themes verify a balanced grid
   ordered GitHub, Bitbucket/GitLab (planned choices may alphabetize among
   themselves); GitHub has **Available** and working **Register GitHub**.
   GitLab and Bitbucket must both display **Planned**, **Not implemented**
   adapter / **Not defined** protocol, with a disabled
   **Registration Unavailable** button. Neither may link to a form.
3. **Adapter** and **Protocol** contain no question-mark help triggers in
   any card. The **Guide** beside the `Choose a Provider` section title
   remains the only Info Tip. Validate Guide desktop hover and keyboard
   focus; click/touch toggles and Escape closes. For Android/Firefox touch
   emulation, test tap rather than desktop pointer hover.
4. At **390×844** and **360×800** inspect card stacking, no horizontal
   overflow, readable metadata, disabled actions and focus-visible states.
5. Click GitHub registration; expect existing provider-owned form. Do not
   submit secrets for this UI-focused scenario. Back navigation must restore
   Source Control context.
6. Run selected Ruff, Ruff Format, djLint, pytest for domain UI, matrix and
   Source Control; run `verify_integration_domain_navigation.py`,
   `verify_sidebar_navigation_standard.py`, `verify_ui_reuse.py`,
   `verify_ui_style.py` if available in the Dev Container.

**Evidence:** exact HEAD SHA, commands/output, 1440×900/390×844
light/dark screenshots, section Guide behavior, absence of Adapter/Protocol
help icons, single-line planned description at 1440×900, disabled-planned
controls, working GitHub destination, any defect.
New candidate executable QA is **NOT RUN** until Dev Container evidence;
Human Visual Acceptance **PENDING**. Official CI/CD and Full Admission
remain **HOLD**.

## 2026-10-25 — #3126 refined design acceptance after screenshot

The operator accepted the domain sidebar selection and three-card direction,
but requested further visual polish: **remove inline question-mark icons from
Adapter and Protocol**, restore the shared KAORI `palette_icon` adjacent to
the section **Choose a Provider**, and shorten the planned-provider explanatory
sentence to `Registration is not yet available.` so it fits one line at
1440×900. The copy still wraps naturally at phone widths; do not force
`whitespace-nowrap` or clip/truncate. The **section-level Guide remains**.

The operator's prior Dev Container evidence for the previous candidate:
`ruff check` PASS; focused pytest **39 PASS**; navigation and sidebar
verifiers PASS. `ruff format --check` reported two formatting issues
(`app/integrations/routes.py` and the Integration UI contract test), and
`djlint --check` reported formatting drift in the shared provider selector.
These specific formatting findings are incorporated into this refinement.
This is source-level correction, **not an assertion of new executable QA PASS**.

Re-test: section icon and text baseline; no help glyph beside Adapter or
Protocol; Guide still opens via keyboard/pointer/touch; shorter planned text
stays one line at 1440×900 and wraps without overflow at 390×844; Available
GitHub CTA works; Planned Bitbucket/GitLab registration remains disabled.
Run Ruff, Ruff Format, djLint, focused pytest, shared sidebar and Integrations
navigation verifiers in Dev Container. Official admission remains **HOLD**;
Human Acceptance **PENDING**.


## 2026-10-25 — #3142 apply accepted Source Control chooser across Integrations

**Human authority:** accepted Source Control provider chooser after #3131.
Operator QA evidence on the accepted candidate: `ruff check` PASS,
`ruff format --check` PASS (2 files formatted), `djlint --check` PASS
(0 files requiring updates), focused pytest **39 passed**, Integration Domain
Navigation PASS, Sidebar Navigation Standard PASS. This evidence belongs
to the earlier Source Control SHA, not to the new cross-domain candidate.

**Reuse audit:** the canonical shared selector
`app/templates/integrations/provider_selector.html` already covers:

- Orchestration / Container Orchestrator (Kubernetes available; planned
  Rancher and Sangfor Kubernetes Engine disabled);
- Observability / Alert Source (Alertmanager);
- Storage / Object, File and Block Storage (matrix-owned availability);
- Registry (Harbor available; other matrix providers planned);
- Secrets Management / Secrets & PKI (Vault available; OpenBao planned);
- Source Control (GitHub available; GitLab/Bitbucket planned).

**Only Observability / Metrics Source diverged.** The existing endpoint
`/integrations/observability/metrics-sources/new` remains stable, but its
`provider_selector.html` now **extends the same canonical template**.
The metrics route projects admitted Prometheus and Thanos provider definitions
into the shared card contract. Provider-specific icon, description, adapter
and **Query Language** occupy the shared card slots rather than a second
implementation. Both approved registration endpoints remain authoritative.
The metrics Guide remains specific to query language/validation; there is
only **one title-level Guide**, with no duplicated Adapter or Query Language
question icons. Hero, section icon, responsive card grid, Available/Planned
badges, disabled buttons, and bottom governance boundary follow the accepted
Source Control style.

**Navigation:** Metrics Source provider selection must keep the Observability
sidebar active with breadcrumb **Integrations → Observability → Choose Provider**
rather than Overview. The Source Control active sidebar/breadcrumb logic
remains unchanged.

**Notification Channels:** retains its existing channel-type selector;
not a member of the infrastructure provider matrix and not redesigned here.

### Acceptance matrix

| Domain | Selector | Main registration path | Verify |
| --- | --- | --- | --- |
| Orchestration | Shared | Kubernetes | Planned choices disabled; cards/Guide |
| Observability — Metrics | Shared, via existing route/template inheritance | Prometheus / Thanos Query | Query Language, Guide, both registration URLs |
| Observability — Alert | Shared | Alertmanager | Active CTA and semantic label |
| Storage | Shared | MinIO | S3 choices, planned disabled |
| Registry | Shared | Harbor | Planned disabled; responsive multi-card |
| Secrets Management | Shared | HashiCorp Vault | Planned OpenBao inert |
| Source Control | Shared (accepted baseline) | GitHub | No visual regression |

Retest 1440×900 light/dark and 390×844 touch, no overflow, Guide pointer/
focus/touch, keyboard controls, correct active sidebar and breadcrumb, and
the existing provider registration forms. Registration credentials and
operational evidence remain a separate domain UAT phase.

### Focused executable check (new candidate, NOT RUN)

```bash
python -m ruff check app/integrations/routes.py app/bootstrap/presentation.py app/common/navigation.py app/common/workspace_navigation.py app/integrations/navigation.py tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py tests/ui/test_source_control_sidebar_navigation_contract.py
python -m ruff format --check app/integrations/routes.py app/bootstrap/presentation.py app/common/navigation.py app/common/workspace_navigation.py app/integrations/navigation.py tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py tests/ui/test_source_control_sidebar_navigation_contract.py
djlint --check app/templates/integrations/provider_selector.html app/templates/integrations/observability/metrics_source/provider_selector.html
python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py tests/contracts/integrations/test_integration_domain_navigation_contract.py tests/ui/test_source_control_sidebar_navigation_contract.py tests/ui/test_source_control_github_app_onboarding_contract.py tests/contracts/integrations/test_metrics_source_routing_audit_20260817_contract.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**New commit Human UAT / executable QA:** PENDING. No claim of PASS until
exact candidate outputs and visual evidence arrive. Official Developer Check,
Full Admission, promotion to staging/main, and release/tag: **HOLD**.
