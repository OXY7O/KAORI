# KAORI — GitHub App Source Control Dev Container UAT

Status: **Candidate only — not human accepted or released**.
Authority: #559, SC-01 #2740, SC-02 #2741, SC-03 #2742; authorization #724.
Branch: `kaori/review/staging-uat`. Official CI/CD remains **HOLD**.

## 1. Local-only admission

The shared temporary UAT aggregation branch now includes the reviewed SC-01/SC-02/SC-03 workstreams and makes the GitHub provider `available` for Dev Container testing. Other Vault/Notification Channels workstreams on this holding branch remain intact. SC-01/SC-02/SC-03 issue work branches and official Draft PRs retain the `planned` lifecycle until formal admission.

Use ignored local APP_ENV=development configuration, never a committed secret file:

- No UAT enable environment variable is required. The shared holding branch's `available` provider matrix enables GitHub directly. Credential registration and installation-specific operations still require an active local super-admin with `integrations.manage` until #724 is admitted.
- `SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=false` — leave HTTP webhook disabled until authenticated signature/replay negatives are reviewed.
- `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED=false` — leave maintenance inbox consumer disabled until worker/crash recovery is reviewed.

Restart Flask, Celery workers and Beat after local flag changes. Register the GitHub App PEM and webhook secret exclusively via KAORI's encrypted form; never place bearer tokens, PEM or raw payloads in JobExecution, logs, committed files or reports.

## Navigation for review

In the Dev Container running this UAT branch, sign in as an active local super-admin and open **Integrations → Source Control → GitHub**. The primary sidebar catalog and active-page/breadcrumb ownership reuse KAORI's existing Integrations navigation; no custom menu was added. GitHub is immediately available for registration and review without `SOURCE_CONTROL_GITHUB_UAT_ENABLED`.

If the new entry is not visible, verify that the running web container uses branch `kaori/review/staging-uat`, restart the Flask web process after checkout, and verify the user has `integrations.manage`. Source Control has now been integrated into `kaori/review/staging-uat` using a reviewed conflict-resolved merge commit. No branch named `kaori/staging` or `main` was changed.

## 2026-10-25 — Source Control Ruff/djLint gate remediation

**Authority:** #3099, scoped formatting follow-up to #3094. Operator's
Dev Container log (before #3099) recorded **33 passed in 4.70s**
for the six Source Control unit/contract suites and **PASS** for
`verify_integration_domain_navigation.py`. Source check results:

| Gate | Observed before correction | Scoped change |
| --- | --- | --- |
| Ruff check | **FAIL**, 3 × I001 | Remove extra blank after import block in three UI test files |
| Ruff format --check | **FAIL**, 2 files | Apply exact quote and one-line assertion formatting |
| djLint --check | **FAIL**, four GitHub templates | Apply exact operator-reported djLint formatting hunks; shared domain template untouched |
| Focused pytest | **PASS**, 33 tests | Test logic unchanged |
| Integration navigation verifier | **PASS** | Provider routing unchanged |

**Scope:** only existing Source Control contract/test source and four
GitHub Jinja templates were formatted. No new page/route, provider,
credential, database, webhook or privilege change. The operator's complete
djLint diff was applied with exact original-line matching to avoid
guessing at indentation or modifying unrelated HTML. No custom
validator or CSS patch.

**Evidence disposition:** source diff/reconciliation PASS; rerun the
existing Ruff, djLint, pytest and integration navigation checks on the
resulting holding SHA. **Do not claim executable PASS before that run.**
The separate Runtime Overview fixed-shell navigation #3097 has its own
Playwright/visual UAT requirement and is not closed by formatting.

## 2026-10-25 — Runtime Overview cross-domain navigation scroll

**Finding / authority:** issue #3097, after Source Control UI review. The
operator reported a white strip beneath Integrations Overview after using
**Runtime Overview** from the Source Control domain. The 1440×900 responsive
screenshot also shows the top of the fixed shell clipped. Source inspection
found the full navigation link contained `#integration-workspace`; the
KAORI app shell intentionally locks root html/body overflow and scrolls
only `main[data-kaori-main-scroll]`. Browser fragment navigation can move
the root scroll unexpectedly, leaving a shell-sized white gap.

**Scoped correction:** cross-page Runtime Overview uses
`url_for('integrations.overview', tab='runtime')` **without a fragment**,
so server-owned selected workspace comes from `?tab=runtime`. The
Integrations Overview Hero Browse Providers / Review Runtime fallbacks
likewise use canonical fragment-free URLs. Existing HTMX
`hx-target`, `hx-select`, `hx-push-url`, server-selected tab and
in-workspace `outerHTML show:none` behavior are preserved. No global
CSS override or custom scroll-reset script is introduced.

**Regression:** existing Integrations Overview contract now asserts
fragment-free navigation without disabling the HTMX selector; existing
Playwright representative-interaction suite includes a cross-page click
and fixed-shell viewport geometry check at 1440×900 and 390×844.

**Evidence:** BEFORE screenshot and source implementation identified;
executable contract / browser tests and updated Human visual UAT PENDING.
After updating Dev Container holding branch, test:

```bash
python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_integrations_overview_workspace_contract.py
python -m pytest -q -s -p no:cacheprovider \
  tests/ui/test_representative_interactions.py \
  -k 'integration_runtime_cross_page_navigation_keeps_outer_shell_in_viewport'
```

Human check: from **Integrations → Source Control**, click
**Runtime Overview** and confirm that Integration Overview opens the
Runtime tab, the header/sidebar top remains fully visible, and no white
strip appears below the shell at the 1440×900 responsive viewport. Repeat
at one narrow viewport and light/dark; browser Back should return to
Source Control. Official CI/CD, Full Admission and staging/main promotion
remain HOLD.

## 2026-10-25 — #3207 Read-first provider workspace entry (supersedes Open CTA only)

**Human UAT correction:** The prior #3106 provider-first registration contract
is **still valid for Add Connection**, but the old shared `Open [provider]`
domain CTA incorrectly sent the operator through Choose Provider before
allowing access to the already-built Integration Coverage/Connection Registry.
The user confirmed this is confusing when no connection exists, because a
read-only overview must not require starting a mutation/registration journey.

Current canonical navigation for all Integration domains:

- **Integrations → Source Control → Open Source Control** opens
  `github_source.index` directly, with overview and coverage/registry
  available even when zero connections exist. Other domains similarly use
  the provider-owned `IntegrationModule.workspace_endpoint` exposed through
  `_integration_type_row` (Kubernetes, Metrics, Alertmanager, MinIO, Harbor,
  Vault). No new provider route, hardcoded product routing or permission
  bypass is introduced.
- **Integrations → Source Control → Add Connection** invokes
  `integrations.choose_integration_provider(integration_type='source_control')`,
  then GitHub provider selection and the source-owned registration form.
  This continues #3106's mandatory provider-first **registration** workflow.
- Existing provider Hero **Register Connection** keeps its current
  provider-owned/selector behavior; normal operational pages read committed
  KAORI state, not mandatory live API reads.
- `components/integration_workspace_tabs.html` renders the existing shared
  section header **Integration Workspace** with the concise description
  **Review committed coverage and registered provider connections.** above
  its Coverage and Connection Registry tabs across seven provider landing pages.
  Shared framed tabs, Alpine state, HTMX, default pagination and accessibility
  stay authoritative.
- Sidebar remains capability/domain first; the new Open navigation does
  not add provider-level sidebar items or change active state/breadcrumbs.

This **supersedes the `Open Source Control → Choose Provider` implication
in the historical #3106 section below**, while preserving that section's
`Add Connection → Choose Provider → registration` requirement. Prior
`#3094` direct registration-first entry is not reinstated.

The same UAT report includes Ruff Check/Format and djLint PASS plus focused
pytest **45 passed / 1 failed**, where the failing source assertion
hardcoded a djLint-sensitive Guide ID. The scoped regression contract now
checks the stable identifier prefix independently of formatting. That prior
test count is not evidence for the updated SHA.

**Dev Container UAT:** after pulling holding, click Source Control in the
sidebar, then Open Source Control (not Add) and verify that GitHub Overview
and Coverage/Registry open with 0 results and a legitimate empty state.
Go back and click Add Connection to confirm the GitHub/Bitbucket/GitLab
provider selector still appears; do not enter secrets for navigation-only
QA. Repeat Open vs Add on Orchestration, Observability (Metrics/Alert),
Storage, Registry, and Secrets Management. Verify 1440×900/mobile,
light/dark, section header above tabs and keyboard/touch navigation.
The old GitHub Test→Register→Toast→Redirect functional UAT remains
independent and pending. Official CI/CD and Full Admission remain HOLD.

## 2026-10-25 — Current approved provider-first navigation (#3106)

The current approved registration journey is **Integrations → Source Control
→ Open Source Control → Choose Source Control Provider → GitHub → Register
GitHub App Connection**. Selection uses the Integration Provider Matrix and
shared `integrations.provider_selector.html`, not a direct-form shortcut.
The GitHub Kernel `workspace_endpoint` remains the zero-argument provider
registry route `github_source.index` for other runtime/nav consumers.
The source domain CTA uses
`integrations.choose_integration_provider(integration_type='source_control')`.
The GitHub overview's registration action also enters the provider picker.

This supersedes the direct-form first-destination rule recorded for
#3094 below. The original source-backed form, CSRF/permission rules,
Test Connection, Save, Full Validation, and scoped installation inventory
remain authoritative and unchanged. Canonical cross-domain UAT is at
`docs/operations/integrations-provider-selection-uat.md`.

## 2026-10-25 — Source Control registration-first workspace and functional QA

**Authority:** Issue #3094, scoped child of reviewed Integrations UI
issue #3085 and correction of #3091's final destination. Operator confirmed
Open Source Control navigation now works but showed that it entered a
staging-oriented provider overview instead of the reusable
**Register Connection** form. The same operator's Dev Container run reported
`ruff check` PASS, `ruff format --check` FAIL (two exact wraps in the GitHub
Kernel unit contract), **24 passed / 1 failed** pytest, and
`verify_integration_domain_navigation.py` PASS. The failing onboarding
assertion expected a hardcoded GitHub link in the shared domain template;
this expectation became obsolete when KAORI switched to
`url_for(item.workspace_endpoint)`.

**Historical #3094 implementation (superseded by #3106):** the provider IntegrationModule
workspace endpoint was then `github_source.new_connection` (existing
`/integrations/source-control/github/connections/new`). The
**Open Source Control** domain CTA then landed on the existing
`Register GitHub App Connection` page using the reusable
`_provider_registration_hero.html`, exactly as the Harbor/Vault
registration forms use it. The GitHub `index` endpoint is preserved
for **Back to Registry**, after-save redirect, connection summary and
authorized **Manage Installations** access. The Source Control workspace
heading is now **Source Control Connections**, while the Provider Registry
tab, shared search/filter/reset, and pagination remain unchanged.

**User-visible terminology:** GitHub provider summary, installation
registry, installation detail and connection form use operational names
rather than `UAT`, `planned` or `design review` placeholders. Internal
`github_source_uat` endpoint names and scoped local-super-admin guard
are intentionally unchanged; normal HTTP GETs still read committed KAORI
data, and Full Validation / repository sync remain governed mutations.
The actual provider lifecycle remains authoritative: disabling provider
registration still blocks credentials. No fake ready state or fabricated
repository count was introduced.

**New regression ownership:** existing Kernel unit and Integrations
onboarding/sidebar/UI contracts now assert registration-first routing,
real Blueprint URL, canonical shared provider link, shared registration
Hero, operational user-visible labels and correct credential/authorization
gates. Obsolete self-route and hardcoded link expectations were corrected.

**QA evidence: NOT RUN on new code**, and no new browser Human Acceptance
has been received yet. Run focused existing gates from a clean updated
holding candidate:

```bash
git rev-parse HEAD
git status --short
python -m ruff check \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/ui/test_source_control_integration_workspace_contract.py
python -m ruff format --check \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/ui/test_source_control_integration_workspace_contract.py
python -m pytest -q -p no:cacheprovider \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/ui/test_source_control_integration_workspace_contract.py
djlint --check \
  app/templates/integrations/partials/_domain_workspace.html \
  app/templates/integrations/source_control/github/index.html \
  app/templates/integrations/source_control/github/form.html \
  app/templates/integrations/source_control/github/uat_index.html \
  app/templates/integrations/source_control/github/uat_detail.html
python scripts/verify_integration_domain_navigation.py
```

**Targeted Human UAT (no real mutation required first):**
1. Open Integrations → Source Control → **Open Source Control** and confirm
   the page is **Register GitHub App Connection** with real form fields and
   working Cancel/Back to Registry navigation.
2. From the Registry, click **Register Connection** and confirm the same
   reusable registration page.
3. In the registered installation overview, confirm **Manage Installations**
   and **Installation Registry** and absence of user-visible temporary
   staging/UAT labels. Review light/dark and mobile layout.
4. For the full functional cycle use only a dedicated approved GitHub App
   test installation, validate identity through **Test Connection**, save
   once, inspect the committed record, then run **Full Validation** and
   repository sync under the existing local-super-admin permission boundary.
   Do not expose PEM, webhook secret, signed token or provider payload.
   Do not enable public webhook ingress for this initial UI verification.

**Hold:** source code/contract authorship is not executable or Human PASS.
Temporary `kaori/review/staging-uat` integration only; no official
Developer Check, CI/CD, Full Admission, staging/main promotion or release.

## 2026-10-25 — Open Source Control self-navigation (historical #3091)

The operator originally found that **Open Source Control** reloaded its own
domain because the Source Control IntegrationModule set
`workspace_endpoint='integrations.source_control'`. Issue #3091 fixed this
self-link by initially routing to `github_source.index`, the existing
GitHub provider landing page, without adding special-case template JavaScript.

**Superseded UAT destination:** after the next operator screenshot, issue
#3094 established **Register Connection** as the correct first action.
At the #3094 checkpoint the canonical IntegrationModule used `github_source.new_connection`
(`/integrations/source-control/github/connections/new`); the provider
`github_source.index` remains an overview/registry for Back to Registry
and after-save navigation. The earlier #3091 test and browser instruction
expecting the landing index as the **first** destination no longer apply.
The #3094 checks above are historical. Use the current #3106 provider-first
journey and runbook instead.

## 2026-10-25 — Source Control domain UI consistency review

**Authority:** scoped UX issue #3085 and operator screenshots comparing the
Source Control domain with accepted Integrations → Registry → Harbor flow.
Three source-level discrepancies were found:

- The Source Control Hero taxonomy copy was longer than neighboring domain
  descriptions. It now uses a concise provider-neutral sentence, with the
  existing shared `page_hero.description_classes()` and normal responsive
  wrapping rather than clipping or `nowrap`.
- The shared `table_registry.clear_filters_link()` was invoked with its
  default `lead=true` so the action rendered `order-first` on the filter
  heading's flex row. Explicit `lead=false` keeps the heading to the left
  and **Clear Filters** on the right, still shown only with active filters.
  Canonical GET/HTMX reset, page 1 and Rows preservation remain unchanged.
- The custom `GitHub · First Provider` and `GitHub · Open Provider` header
  items were redundant beside the canonical provider workspace action.
  Only the existing `Open Source Control` integration type link remains.

**Focused regression ownership:** the existing
`tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py`
now contains scoped assertions for compact taxonomy copy, one provider
workspace action, and Clear Filters order/conditional/HTMX query semantics.
Previous contracts verify shared UI primitives but did **not** enforce all
three criteria, so they cannot be claimed as pre-existing passes.

**2026-10-25 operator Dev Container evidence:** source fixes are visible in
the supplied **desktop** screenshot: compact one-line Hero description,
**Clear Filters** at the right of the header with an active search, and only
one **Open Source Control** action. The user also supplied these checks:

- `ruff check` on the focused UI contract: **PASS**.
- `ruff format --check`: **FAIL** — three string-quote adjustments required
  in the contract file, with exact formatter diff provided.
- Focused Integration domain/navigation/pagination/Source Control contract
  pytest: **19 passed in 2.33s**.
- `djlint --check` on the two shared Integration templates: **PASS** —
  0 files would be updated.
- `scripts/verify_definition_registry.py`: **PASS** — Definition Registry
  v1.1 (61 rules, 67 permissions, 19 jobs, 6 integration domains, 36 provider
  capabilities and the existing qualification/compatibility catalog).

The three exact Ruff quote edits were committed under #3085. **Executable
post-fix Ruff format verification is PENDING** on the resulting holding SHA.
The pasted operator output did not include a same-run `git rev-parse HEAD`,
so do not attribute its 19 tests to an unverified exact SHA.

**Remaining scoped Human UAT:** verify actual Clear Filters **click** resets
the active search while preserving Rows=5, confirm **Open Source Control**
navigation, and check light/dark plus narrow/mobile layout. Their behavior
must not be declared Human PASS from the single screenshot or source review.
No GitHub App credentials or background provider jobs are needed.

```bash
git rev-parse HEAD
git status --short
python -m ruff check tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py
python -m ruff format --check tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py
python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py \
  tests/contracts/integrations/test_provider_registry_pagination_contract.py \
  tests/ui/test_source_control_integration_workspace_contract.py
djlint --check \
  app/templates/integrations/partials/_domain_workspace.html \
  app/templates/integrations/domain.html
python scripts/verify_definition_registry.py
```

**Delivery:** temporary `kaori/review/staging-uat` UAT only; no new
component, changes to GitHub integration provider credentials, HMAC,
webhooks, database/worker or provider readiness, and no official CI/CD,
Full Admission, promotion or release until explicit human authorization.

## 2. Existing Developer Check — commands to run

To update the shared holding branch without discarding other reviewed UAT workstreams:

```bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
```

GitHub App review does **not** require `SOURCE_CONTROL_GITHUB_UAT_ENABLED`; continue keeping the webhook ingress and consumer disabled during initial testing.



```bash
git branch --show-current
git status --short
python scripts/verify_migration_graph.py
python scripts/verify_definition_registry.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_celery_topology.py
python scripts/verify_template_dependencies.py
python scripts/verify_python_syntax.py
python -m ruff check app/source_control app/models/source_control.py app/integrations/source_control tests/unit/test_source_control_*.py tests/ui/test_source_control_*.py
python -m ruff format --check app/source_control app/models/source_control.py app/integrations/source_control tests/unit/test_source_control_*.py tests/ui/test_source_control_*.py
python -m pytest -q --tb=short tests/unit/test_source_control_*.py tests/ui/test_source_control_*.py
python -m pyright --project pyrightconfig.json
bash scripts/quality_gate.sh --static
```

These are **not evidence of execution**. Use existing Developer Check planner and widen gates when migration, shared Kernel/Flask bootstrap or security boundaries change. Record exact SHA, failures and remediation evidence.

## 3. Database migration (controlled)

Never use normal app credentials for Alembic; never reset the PostgreSQL volume. Use approved Dev Container migrator per `docs/DEVELOPMENT.md` from the supported host directory:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
```

Expected revision chain: `20261023_scope_policy_storage → 20261023_channel_retire → 20261023_sc_identity → 20261023_sc_app_credential → 20261023_sc_webhook_delivery → 20261023_sc_repo_collection → 20261023_sc_webhook_job_link`.

The pre-existing `20261023_channel_retire` Alembic parent is retained byte-identically from this holding branch. The Source Control migration children were added after this approved parent. Verify upgrade/downgrade on an explicitly disposable PostgreSQL database, not user data.

## 4. Worker preflight

Existing queues: `inventory` (GitHub sync), `integration-validation` (Full Validation), `integration-runtime` (health refresh) and `maintenance` (optional signed-webhook consumer). The registered job `source_control.repository.sync` policy and both webhook flags start **disabled**.

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
celery --app celery_worker:celery_app inspect registered
celery --app celery_worker:celery_app inspect active_queues
```

Check `app.integrations.source_control.tasks.sync_source_repositories` on the inventory worker and the existing validation task on its worker. Canonical JobExecution must reject dispatch when its exact worker is unregistered.

## 5. Full functional UAT

1. Open `/integrations/source-control/github/` and register a real, limited-permission GitHub.com App installation via the encrypted form. Confirm Test Connection does not fabricate inventory readiness.
2. Sign in as an active **local super-admin**, open `/integrations/source-control/github/uat/`, select an installation and run **Full Validation**. Observe canonical JobExecution and require metadata + Contents read for connection readiness.
3. Run **Sync Repositories**, follow canonical JobExecution progress and review `/integrations/source-control/github/uat/installations/<record-id>`. Verify default 5-row pagination (5/10/25/50), HTMX, loading/empty/error state and light/dark/responsive design.
4. Test Unknown before complete collection versus a provably empty installation, All/Selected grants, rename/transfer/archive, access-lost-not-deleted, stale-generation ordering and retention of committed inventory after partial/rate-limit errors.
5. Confirm exact SHA plus observation timestamp from a native-ID-qualified default-branch check. SHA collection is bounded to 20 refs/run: missing/unchecked SHA must be Unknown and job partial, not full-history completeness.
6. Repeat using an independent GitHub App installation under a **second organization**. Prove no cross-installation repository leak. Ordinary users and SSO administrators must be denied from the UAT workspace.
7. Review keyboard/accessibility, mobile/tablet/desktop layout, dark/light themes, masked credentials, worker failure states and notification feedback.


The UAT inventory table polls committed KAORI state every 15 seconds via the installation-scoped HTMX GET route; it does not call GitHub. The installation detail now shows the latest five signed delivery receipts, correlation to canonical JobExecution, and recovery state, without raw payloads. Registration and UAT views are restricted to local super-admins until #724 is admitted. Revision gaps count every eligible repository even though only 20 default-branch tips are requested per run.

## 6. Signed webhook (separate controlled UAT)

Only after local HMAC/replay negatives pass, opt into `SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=true`; HTTP 202 is a **committed delivery receipt**, never successful source reconciliation. Test no/malformed signature, wrong installation, UUID replay/collision, oversized body, rate limit and revoked App.

Only after worker/recovery review, opt into `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED=true`. Test queued/partial/failed/canceled terminal JobExecution mapping, 5-minute preclaim backoff, three-attempt review, ambiguous-dispatch quarantine, and retention of previous committed repository scope after failure. Never expose the Dev Container publicly or point a production GitHub App to it without network/security approval.

## 7. Acceptance evidence and release boundary

Collect SHA, migration graph and DB upgrade/downgrade, `ruff`/`pytest`/`pyright`/`djlint`/verifiers, queue registration, two redacted real installation scopes, JobExecution IDs/status, HMAC negative results and UI screenshots in both themes. Record FAIL and remediation separately. **Human acceptance is mandatory** for this user-visible and security-sensitive integration.

The code is assembled on the shared **temporary** `kaori/review/staging-uat` holding branch for Dev Container UAT. No merge to official `kaori/staging` or `main`, no official CI/CD admission and no production flags until explicit authorization.


## 2026-10-25 — #3145 canonical GitHub App registration form polish

**Visual finding:** The operator's Register GitHub App Connection screenshot
showed a flat fieldset with a detached validation sidebar carrying Cancel,
Test Connection and Register Connection buttons. This was inconsistent with
the approved MinIO/Harbor/Alertmanager KAORI registration archetype.

**Fix scope:** The GitHub form keeps `registration_hero.render` and the
provider-owned Flask-WTF fields but now uses the canonical
`integration_ui.section_shell_classes`, `integration_ui.palette_icon`,
`operational_toggle.render`, `form_action_bar.render`, `action_button.classes`,
`operational_callout.render` and `registration_context.render`.
Its primary card contains **Connection Identity → GitHub App Installation →
App Credentials → Operational Controls**, followed by the action footer;
the sticky right column is dedicated to **Registration Flow** and external
provider authority. No new UI controller or one-off design tokens.

**Security boundary preserved:** CSRF hidden token and gated fieldset,
`name=action` /`value=test|save` submit actions, server RBAC and local
super-admin UAT authorization, 409 for unadmitted provider, required App PEM /
webhook secret fields, secret clearing after POST, identity recheck during
save, and encrypted-at-rest credentials remain unchanged. GitHub currently
rechecks identity on Save, so do **not** substitute MinIO/Harbor's
`provider_registration_actions` proof-gated component, which requires a
different verified-payload lifecycle.

**Bundled QA repair for #3142:** Earlier cross-domain Metrics Source evidence
reported Ruff check PASS, Ruff Format **4 unformatted files**, djLint
**1 file**, pytest **41 PASS / 1 FAIL** (stale literal Protocol label
assertion), Integration Domain Navigation PASS and Sidebar Standard PASS.
The expected Ruff/djLint formatting changes and flexible Protocol /
Query Language assertion were applied separately and are not claimed
as executable verification on this new candidate.

### Exact-candidate Dev Container QA

```bash
git rev-parse HEAD
git status --short
python -m ruff check app/common/navigation.py app/integrations/navigation.py \
  app/bootstrap/presentation.py app/common/workspace_navigation.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
python -m ruff format --check app/common/navigation.py app/integrations/navigation.py \
  app/bootstrap/presentation.py app/common/workspace_navigation.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
djlint --check app/templates/integrations/provider_selector.html \
  app/templates/integrations/observability/metrics_source/provider_selector.html \
  app/templates/integrations/source_control/github/form.html
python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/contracts/integrations/test_metrics_source_routing_audit_20260817_contract.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**Human Visual QA:** 1440×900 and 390×844, light and dark, keyboard
focus and touch. Check section headers/icons, field labels and errors,
Cancel/Test/Register footer alignment, registration-flow sidebar, scroll/
overflow, and clear masking of PEM and webhook secret. With no secrets,
verify that registration page loads and forms are not accidentally
submitted. With an approved **test** GitHub App only, separately test
negative/positive Test Connection and Register behavior with redacted
evidence. Provider admission and Full Validation remain independent gates.

**Exact candidate executable QA / Human Acceptance:** PENDING. Source review
alone does not count as completion. No official CI/CD, Full Admission,
staging/main promotion, release/tag or infrastructure mutation.


## 2026-10-25 — #3145 Kubernetes-aligned GitHub registration UAT refinement

**Authority:** #3145 follow-up to #3148. Operator supplied side-by-side
1440×900 screenshots of the accepted Kubernetes connection registration and
the newer GitHub App form. GitHub already has canonical identity and sidebar
content, but lacks the cohesive bordered **Endpoint & Access** region with
**Test Connection in its header**, and its footer remained crowded.

**Design applied:** The GitHub form continues using the shared registration
Hero and 8/4 responsive grid. Connection Identity stays at the top. Installation
identity, App PEM and webhook secret, and operational enablement are grouped
inside one bordered **Installation & Access** surface using the same
`components/connection_validation_header.html` component as Kubernetes.
`Test Connection` moves from the bottom footer into this surface header.
The shared `form_action_bar` footer now only contains Cancel and
Register Connection, with an accurate note that GitHub **revalidates on
registration**. The right sticky panel keeps the shared four-step Registration
Flow and Related Operational Workspace composition. Component and responsive
tokens come from existing KAORI patterns; no new CSS/JS is introduced.

**Do not conflate functional contracts:** Kubernetes/MinIO/Harbor registration
depends on a time-bound connection-test proof and disables Register until the
proof is available. GitHub has **no such proof field**: the existing server
verifies identity/permissions again in `action=save`. This visual alignment
must not fabricate a proof gate, separate endpoint, or a false "test required"
claim. `action=test`, `action=save`, CSRF, fieldset admission guard, server
RBAC/local-super-admin UAT, masked credentials and clear-sensitive-after-POST
are unchanged.

**Bundled known QA repairs (previous candidate):** operator reported Ruff
check PASS, Ruff Format FAIL on GitHub UI test, djLint FAIL on GitHub form,
pytest **42 passed / 1 failed** due to an obsolete Metrics Source assertion
expecting `default('Protocol')`, and both navigation verifiers PASS.
This follow-up aligns exact known formatting changes and updates the
Metrics Source contract to the approved djLint form `default("Protocol")`.
Do not count previous results as proof of this new candidate.

### New candidate verification

```bash
git rev-parse HEAD
git status --short
python -m ruff check \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py
python -m ruff format --check \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py
djlint --check \
  app/templates/integrations/source_control/github/form.html \
  app/templates/integrations/provider_selector.html \
  app/templates/integrations/observability/metrics_source/provider_selector.html
python -m pytest -q -p no:cacheprovider \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py \
  tests/contracts/integrations/test_metrics_source_routing_audit_20260817_contract.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

Visual checks: compare Kubernetes and GitHub at 1440×900 and 390×844,
light/dark, ensuring consistent Section Header, bounded Installation & Access,
right flow cards, field hierarchy, Test Connection header action, footer
alignment, no horizontal overflow, keyboard focus, visible errors, and no
secret exposure. Use a deliberately invalid test credential for negative
submit test only in a controlled UAT environment. Positive Test/Register
with real secrets belongs to authorized functional UAT; redact evidence.

**Executable QA and Human Visual Acceptance on this new SHA:** PENDING.
Official Developer Check, Full Admission, `kaori/staging`/main promotion,
release/tag and infrastructure mutation remain HOLD.


## 2026-10-25 — #3164 GitHub App connection-test proof admission

**Authority:** Human UAT explicitly superseded the prior UI-only registration
pattern in #3145 after viewing the accepted Kubernetes provider form. The
GitHub App footer must show the canonical **Connection Test Required**
status, with **Register Connection disabled until a successful Test Connection**
for the exact form values. Registration must enforce this rule server-side.

**Implementation:**
- GitHub Test Connection uses the existing `/integrations/source-control/github/connections/new`
  route via HTMX to avoid re-rendering or clearing user-entered PEM/webhook
  secret from the live browser form. It sends the same CSRF-protected Flask-WTF
  fields and action=test; server response is a sanitized, inline KAORI
  success/error callout and an `HX-Trigger` containing only a signed proof.
- Proof issuance is possible only after the real GitHub App installation
  probe succeeds. Token is issued with `itsdangerous.URLSafeTimedSerializer`,
  GitHub-specific salt, 10-minute maximum age, invoking user ID, and an
  application-keyed HMAC-SHA256 fingerprint of **all form values**, including
  the secret fields. The token never serializes PEM, webhook secret,
  access tokens, or unkeyed credential hashes.
- Alpine uses the existing Kubernetes-style `connectionVerified`
  state and shared `_provider_registration_actions.html` footer. Any input
  or change to the form invalidates the local proof and disables Register;
  a new successful test emits `github-connection-tested`, restoring proof.
- Server Save now rejects missing, expired, tampered, cross-user and
  changed-configuration proofs with 409 (no persistence); when valid, the
  existing `save_tested_connection` performs a fresh live GitHub installation
  validation before writing a **validation_required** connection. A proof
  never implies Full Validation or committed repository inventory.
- Right Registration Flow copy is shortened to fit one line at the
  reviewed desktop width: `Register a tested GitHub App.`,
  `Save, then run Full Validation.`, `Test verifies identity and scope.`.
  Small viewports wrap naturally without clipping.
- No webhook flags, migration, provider admission, JobExecution or
  external provider mutation changed.

**Important security and lifecycle distinction:** The proof is a short-lived
successful **pre-save test**, not a provider access token or substitute for
KAORI Full Validation. After proof expiry, the backend blocks registration
even if the client still displays a success status. Page reload resets
client-side test state. Save does not trust client-side Alpine state.

### Focused exact-SHA Dev Container checks

```bash
git rev-parse HEAD
git status --short
python -m ruff check \
  app/integrations/source_control/source_control/providers/github/application/routes.py \
  app/integrations/source_control/source_control/providers/github/application/registration_proof.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/unit/test_source_control_github_registration_proof.py
python -m ruff format --check \
  app/integrations/source_control/source_control/providers/github/application/routes.py \
  app/integrations/source_control/source_control/providers/github/application/registration_proof.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/unit/test_source_control_github_registration_proof.py
djlint --check \
  app/templates/integrations/source_control/github/form.html \
  app/templates/integrations/source_control/github/partials/_connection_test_result.html
python -m pytest -q -p no:cacheprovider \
  tests/unit/test_source_control_github_registration_proof.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/unit/test_source_control_github_kernel_contract.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**Human Functional + Visual UAT (redacted test GitHub App only):**
1. Fresh form: footer displays Connection Test Required; Register Connection
   is disabled. No proof is issued by GET.
2. Invalid form or bad GitHub App credentials: Test returns a sanitized error
   in-page, no secret reflection, no issued proof, Register stays disabled.
3. Successful Test: inline success, status becomes Connection Verified, Register
   becomes active. Inspect network only for absence of raw credential material
   in response body, `HX-Trigger` and proof; submitting form naturally still
   sends the entered credentials to the authorized KAORI endpoint.
4. Edit any field (including App ID, installation/account IDs, name,
   environment, description, PEM, webhook secret, enabled checkbox):
   proof clears and Register becomes disabled until retested.
5. Forge direct Save POST without proof, invalid proof, a proof for different
   values/user, or expired proof: server refuses registration; no canonical
   identity is saved. Verify with authorized testing evidence.
6. With matching valid proof, Save MUST independently revalidate live grants
   before writing a connection. Success does not mark readiness as Ready;
   Full Validation remains a separate step.
7. Review 1440×900 and 390×844 in both themes, keyboard focus and touch:
   aligned shared header/footer/actions, concise flow descriptions, no card
   overflow, no stale credential in rendered response.

**Source/merge checks and local executable/Human UAT are separate.** Do not
claim a clean gate or Human Acceptance before exact-SHA Dev Container output.
Official Developer Check, Full Admission, staging/main promotion and release
remain **HOLD**.


## 2026-10-25 — #3167 HTTP 400 on Register after successful Test Connection

**Observed Human UAT:** GitHub App Test Connection succeeded and enabled the
Register Connection action, but Save navigated to the browser's unstyled
`400 Bad Request` response. The GitHub App installation credentials and
disabled webhook are **not** the cause.

**Root cause:** KAORI's shared `app/static/js/application_shell.js` changes
the pressed `data-operation-submit` button to `disabled` in the native
`submit` event before the browser constructs the outgoing FormData.
Because the shared registration footer uses the clicked button as the
named submitter `name="action" value="save"`, disabling that submitter drops
`action=save` from the POST. The Source Control backend deliberately rejects
unknown/missing action using `abort(400)`. The earlier Test Connection is
a separate HTMX button and is unaffected.

**Fix:** The existing shared submit-loading handler now installs a one-shot
native `formdata` event listener to preserve the selected named
submitter's `name=value` before disabling it. It uses
`formData.set(name, value)` for only the chosen submitter. No static
hidden `action=save`, no backend fallback accepting missing actions,
no change to the HTMX `action=test` request, no additional JS/controller,
no provider adapter or credential change. Unnamed submit buttons retain
their existing behavior.

**Existing quality gates/retest:**
```bash
git rev-parse HEAD
git status --short
python -m pytest -q -p no:cacheprovider \
  tests/contracts/design/test_application_shell_interaction_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/unit/test_source_control_github_registration_proof.py
python -m ruff check \
  tests/contracts/design/test_application_shell_interaction_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
python -m ruff format --check \
  tests/contracts/design/test_application_shell_interaction_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
python scripts/verify_javascript_syntax.py
python scripts/verify_application_shell_standard.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**Human UAT:** restart Flask after pulling this holding SHA. A new page
reload clears the earlier proof, so fill the GitHub App form and perform
Test Connection again, then click Register within the ten-minute proof
window without editing fields. Expect navigation to the GitHub Source
Control registry, a newly registered `validation_required` connection,
and then the separate Full Validation stage. Do **not** submit the PEM,
webhook secret, signed proof, browser network body or raw request headers
as GitHub issue/UAT evidence. Only share redacted screenshots and
credential-free status/error summaries.

**Regression scope:** verify existing operational form buttons that use
`data-operation-submit`, including unnamed submitters; failed/missing
proof still rejected by GitHub and none of the original credential/CSRF
checks are weakened. Executable checks and Human Acceptance for the new
exact SHA are **NOT RUN/PENDING** pending Dev Container evidence.
Official CI/CD / Full Admission / staging/main promotion remain HOLD.


## 2026-10-25 — #3172 Test Connection toast + proof drift after native Save

**Human finding:** Operator completed GitHub App Test Connection (with webhook
inactive). The inline callout and shared footer showed Connection Verified,
but clicking Register displayed `Connection Review: Connection settings
changed after testing. Run Test Connection again.` instead of committing,
queuing a success toast and redirecting. Operator explicitly requests
**KAORI toast for successful Test Connection**, and **toast + redirect for
successful Register Connection**.

**Serialization correction:** HTMX and native browser form submission can
serialize textarea line endings differently (LF, CRLF or CR). The
GitHub-specific, HMAC-protected proof fingerprint now normalizes only
`description` and `private_key_pem` multiline line endings to LF before
fingerprinting. This does **not** change the PEM supplied to GitHub, saved
encrypted credentials, or the strict comparison of all other fields. An
actual changed secret, identity, enabled state or description still rejects
the proof. Expiration, user binding and signed-proof integrity remain.

**Feedback:** The GitHub HTMX Test Connection result reuses
`components/operational_toast.html` with an out-of-band swap into
`#operational-toast-stack`; it no longer renders a duplicate inline
Connection Verified/Not Verified callout. The shared footer remains
Connection Test Required / Connection Verified as an **action-state**
indicator. A successful Register already executes the provider-owned live
identity recheck, persists the installation in `validation_required`,
records `source_control_connection_registered` with
`queue_feedback=True`, and redirects to `github_source.index`. This
existing queued feedback appears through the shared toast stack after the
redirect; no new ad-hoc notifications or success-before-save paths.

**Previous executable evidence:** Operator ran Ruff check PASS; Ruff
format FAIL on one onboarding contract; pytest **23 passed**, JavaScript
syntax PASS, Application Shell Standard PASS, Integration Navigation PASS,
Sidebar Standard PASS. This finding is tracked separately from code
delivery and does not qualify a new SHA as UAT Accepted.

### Exact candidate QA

```bash
git rev-parse HEAD
git status --short
python -m ruff check \
  app/integrations/source_control/source_control/providers/github/application/registration_proof.py \
  tests/unit/test_source_control_github_registration_proof.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
python -m ruff format --check \
  app/integrations/source_control/source_control/providers/github/application/registration_proof.py \
  tests/unit/test_source_control_github_registration_proof.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
djlint --check \
  app/templates/integrations/source_control/github/partials/_connection_test_result.html
python -m pytest -q -p no:cacheprovider \
  tests/unit/test_source_control_github_registration_proof.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/contracts/design/test_application_shell_interaction_contract.py
python scripts/verify_javascript_syntax.py
python scripts/verify_application_shell_standard.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**Human UAT:** Fresh GET, re-enter secrets locally; Test Connection shows
one KAORI success toast and shared footer becomes Connection Verified with
Register enabled. Do not edit any input before clicking Register. Browser
should redirect to GitHub Source Control index and display a queued KAORI
success toast. Verify canonical installation and
`validation_required` readiness. Check edited real PEM/password/any input
still invalidates proof and disables Save. Expired/missing/different user
proof still cannot save. No PEM, webhook secret or signed proof in issue,
logs, screenshots, or network evidence shared outside Dev Container.

**Admission:** exact merged candidate executable QA and Human Acceptance
PENDING until operator verifies. Official CI/CD, Full Admission,
`kaori/staging`, main and release/tag remain HOLD.


## 2026-10-25 — #3177 canonical GitHub Integrations registry after Save

**Human authority:** Operator identified Alertmanager Integrations as the
accepted list/overview reference, requiring GitHub Source Control to display
the **same KAORI shared UI** instead of a standalone frontpage and separate
generic UAT installation list. The user expects successful Register Connection
to queue a **success toast** and redirect to the new GitHub Integration list.

**Implementation reused** (without new palette/taxonomy): shared
`integrations/components/_provider_frontpage.html` hero and overview;
`components/integration_workspace_tabs.html` for Integration Coverage /
Connection Registry; `integrations/components/_workspace.html` section
shells and KPI cards; `integrations/components/_provider_registry.html`,
`components/table_registry.html`, `components/table.html` and
`components/states/_empty_state.html` for registry/table filters and
pagination. The hero gained an **optional** association label and description
so GitHub accurately displays **Repository Grants** without misrepresenting
them as **Consumer Bindings**; every existing provider retains its defaults.

**Committed-only read path:** `github_source.index` queries
`IntegrationInstance` for counts and paginated (default 5) connection rows,
`SourceInstallation` for installation identifiers/selection, and current
`SourceRepositoryGrant` for committed grant counts. Nothing fetches the
live provider during a normal GET. Search/name/description, Environment and
Readiness filters use the shared HTMX registry semantics. The real state
`validation_required` is distinct from a successful pre-save Test Connection.
Coverage does not claim repositories are completely inventoried when no
committed grant observation exists.

**RBAC:** Source Control index remains `integrations.manage` protected.
The existing privileged `github_source_uat.detail` Manage action only
appears when the user also satisfies the Dev Container UAT authorization
guard. No privileged endpoint is exposed or expanded by the UI change.
Planned providers still show Not Observed instead of zero-ready fabrication.

**Save → toast → registry:** Existing `save_tested_connection(values)`
performs live recheck and commits first; the existing
`record_operational_activity(queue_feedback=True)` queues a success toast,
then `redirect(url_for('github_source.index', tab='registry'))` opens the
new canonical Connection Registry. This does not mean the earlier observed
proof-drift defect is automatically Human Accepted; Test→Save→Redirect needs
its own exact-SHA evidence. Webhook may remain OFF.

### Exact Dev Container checks

```bash
git rev-parse HEAD
git status --short
python -m ruff check \
  app/integrations/source_control/source_control/providers/github/application/routes.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
python -m ruff format --check \
  app/integrations/source_control/source_control/providers/github/application/routes.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
djlint --check \
  app/templates/integrations/components/_provider_frontpage.html \
  app/templates/integrations/source_control/github/index.html \
  app/templates/integrations/source_control/github/partials/_connection_registry.html
python -m pytest -q -p no:cacheprovider \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/contracts/integrations/test_provider_registry_pagination_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**Human UAT checkpoints:**
1. Open GitHub Integrations with zero saved connections: same family of Hero,
   overview, two framed tabs, Setup Required empty state and no false
   ready/inventory coverage. Available Register action still opens GitHub App.
2. Register using approved GitHub App test-only credentials: Test Connection
   uses canonical toast, proof gate enables Register, Save persists, queues
   success toast, then redirects to **GitHub Integrations → Connection
   Registry**. Check saved connection appears with **Validation Required**
   (not Ready), correct environment and installation identity.
3. Filters (name/environment/readiness), Clear Filters, pagination 5/10/25/50,
   no duplicate rows, stable URL on HTMX and full GET, responsive/light-dark.
4. Open Manage only as approved super-admin within Dev Container; unprivileged
   users cannot navigate directly to UAT detail routes. Do not show PEM,
   webhook secret, signed proof, or network request bodies in evidence.
5. Full Validation remains subsequent separate functional UAT; committed
   repository access is not invented from live installation selection.

**Validation boundary:** GitHub source/diff inspection is not executable
Dev Container QA or Human Acceptance. Official Developer Check, Full
Admission, `kaori/staging`, main, and release/tag remain HOLD.


## 2026-10-25 — #3177 Coverage parity correction before GitHub App registration

**Human visual authority:** The operator compared approved Kubernetes Integration
Coverage (table + search/filter + status + five-row pagination) with the
GitHub Coverage tab created in #3179 (three KPI cards and information box).
The latter was rejected as **UI inconsistency / Visual UAT FAIL**.
Do not create a different coverage layout for Source Control: only the
domain-specific columns and evidence semantics may differ.

**Implementation:** GitHub Coverage now reuses the existing Kubernetes
coverage template archetype and shared components:
`_provider_registry.registry_header/search_field/select_field/
asset_coverage_table_classes/asset_coverage_colgroup/pagination_footer`,
`table.html`, `table_registry.html`, `_semantic_status.html`,
`_workspace.html` and `components/states/_empty_state.html`.
The six columns are **Repository, Installation, Environment, Access,
Evidence Coverage, Actions**, with a separate query and paging state
(`coverage_q`, `coverage_environment`, `coverage_status`,
`coverage_page`, `coverage_per_page`) and default **5 rows**.
The existing **Connection Registry** remains independently filtered and
paginated; HTMX swaps target the section that owns the controls.

**Evidence boundary:** Rows are sourced only from joined, current
`SourceRepositoryGrant` / `SourceRepository` /
`SourceInstallation` / `IntegrationInstance` and
`SourceRepositoryCollectionState` with
`committed_generation > 0`. This is **not** a live GitHub repository API
read, a trial App Test Connection, nor a proxy for complete repository access.
The coverage field is the committed collection's explicit coverage;
access reflects the stored grant status; readiness reflects Full Validation.
When no collection has committed a generation, the standard table + empty
state say **No GitHub Repository Coverage Observed**. If an existing
committed collection has zero active grants, the empty state instead says
**No Repositories in Committed Coverage**. Unregistered GitHub Apps
must never create synthetic repository rows.

**Access:** Only an existing authorized local Dev Container UAT super-admin
can see a per-installation View Details link; existing
`github_source_uat.detail` resource guard remains authoritative.
No new endpoint, webhook, credential or provider mutation introduced.

**Related QA repair:** Operator evidence on prior #3179 SHA: Ruff Check
PASS; Ruff Format FAIL for `application/routes.py` and GitHub UI contract;
djLint FAIL for GitHub `index.html` and `_connection_registry.html`;
pytest **28 PASS / 1 FAIL** because a stale test demanded a direct
`components/page_hero.html` import instead of using shared
`provider_front.hero`; both navigation verifiers PASS.
The old KPI-only coverage markup was replaced with the accepted table
archetype, registry djLint diffs applied, route Ruff formatting corrected,
and UI contracts changed to assert shared ownership. These are **source
changes, not a claim that new SHA QA has passed**.

### Exact candidate Dev Container checks

```bash
git rev-parse HEAD
git status --short
python -m ruff check \
  app/integrations/source_control/source_control/providers/github/application/routes.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
python -m ruff format --check \
  app/integrations/source_control/source_control/providers/github/application/routes.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py
djlint --check \
  app/templates/integrations/source_control/github/index.html \
  app/templates/integrations/source_control/github/partials/_connection_registry.html \
  app/templates/integrations/source_control/github/partials/_integration_coverage.html
python -m pytest -q -p no:cacheprovider \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py \
  tests/contracts/integrations/test_provider_registry_pagination_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**Human UAT before registration:** open
**Integrations → Source Control → GitHub → Integration Coverage** at
1440×900 and 390×844, light/dark. Confirm familiar Kubernetes-style
six-column table, Environment/Coverage filters and Search, pagination
Showing 0–0 of 0 and Rows 5 when no committed grants, inline empty state
within table, correct active tab/sidebar, keyboard/touch controls,
no horizontal viewport overflow. Switching tabs and filtering must not
destroy the independent Connection Registry filters or pagination.
Zero grants before registration must **not** be displayed as Ready.
After actual registration and subsequent synchronization, verify source
identity, effective grant status and committed collection coverage with
read-only evidence. GitHub App creation/test/save UAT remains independently
open; no credentials or proofs in QA screenshots/logs.

**No official admission:** Developer Check, Full Admission, `kaori/staging`,
main promotion, deployment/release and production mutations remain HOLD.
Human Acceptance **PENDING** until exact-SHA executable checks and
operator visual review.


## 2026-10-25 — #3232 Registration identity row and post-save coverage guidance

**Human UAT evidence:** The operator successfully registered a GitHub App
connection. The registry displayed one installation with **Validation
Required**, while repository Coverage correctly remained **0**. These are
distinct stages, **not** proof that GitHub repository access was rejected.

1. **Test Connection** confirms installation identity and scope but does not
   create persisted inventory evidence.
2. **Register Connection** persists a canonical GitHub App connection,
   source installation identity, and encrypted app credentials. It does not
   launch Full Validation or an inventory collection.
3. **Full Validation** is the separate provider-owned validation job.
   Open **Integrations → Source Control → GitHub → Connection Registry →
   Manage**, then select **Full Validation**. Observe actual JobExecution
   status; do not infer success from the button request. Access remains
   restricted to the authorized local-super-admin workflow.
4. Once Full Validation has succeeded, select **Sync Repositories** from
   the same installation detail. This invokes the existing canonical
   `source_control.repository.sync` inventory job under resource-scoped
   admission and a registered worker. The job's policy is **disabled by
   default**: do not silently enable it or bypass worker/job admission
   during this visual UAT. A `sync_blocked` or `validation_blocked`
   feedback means investigate JobExecution/worker/policy readiness
   separately, without performing hidden infrastructure mutations.
5. Check the collection's **committed generation**, current effective-dated
   repository grants and outcome. Only then return to **Integration
   Coverage**. This page intentionally reads committed KAORI state with
   `SourceRepositoryCollectionState.committed_generation > 0`, and
   `SourceRepositoryGrant.valid_until IS NULL`. It never invents rows
   from successful Test Connection, an installation's Selected repository
   scope, or a queued job.
6. With **one or more registered connections and no committed collection**
   the UI now says **Complete Full Validation, then Sync Repositories to
   commit repository access evidence.** and points to **View Connections**,
   rather than suggesting a second registration. The 0-connection state
   retains the Register Connection call-to-action; a genuinely committed
   but empty collection retains its different empty state.

**Form UI:** GitHub App ID, Installation ID and Organization/Account ID
share a `sm:grid-cols-2 xl:grid-cols-3` identity row on desktop, stacking
to one column on phones. No change to value semantics, registration proof,
PEM, webhook-secret storage, CSRF or validation.

**Previous QA failures resolved in source:** Operator reported two Ruff
Format differences in integration navigation/provider contract tests; one
stale `&amp;` literal in shared-heading test after approved macro
extraction; djLint indentation in `integration_workspace_tabs.html`
and `integrations/domain.html`. Correct those exact deviations without
restoring duplicated title markup. These fixes require new SHA executable
checks; last operator 44-pass/1-fail output is historical, not current QA.

**Human UAT:** 1440×900 GitHub registration form shows one row of the
three ID fields; narrow viewport remains usable. Registered state shows
a truthful Validation Required in Connection Registry and guidance in
Coverage. After a successful authorized Full Validation and permitted
repository sync, committed repository records appear or the UI reports
a committed-but-empty observation; do not equate an empty authorized
collection with an unobserved collection. Observe toast, access rights,
empty state, full revision evidence and keyboard/touch behavior separately.
Official CI/CD, admission, staging/main promotion and release remain HOLD.


## 2026-10-26 — #3246 GitHub Provider Registry Open and Manage Integration parity

**UAT finding:** The Source Control domain Provider Registry `Open` action
for a registered GitHub installation returned to
`/integrations/source-control` instead of a connection detail. Its
provider kernel `_detail_url` was still the historical placeholder.
The **correct** detail URL now targets the matching native
`SourceInstallation.id` through `github_source_uat.detail`, **only**
for an active authorized local database super-admin with
`integrations.manage`. For all other readers, the descriptor links to
the provider-owned GitHub Overview; the installation route continues to
enforce `require_uat_access()`. The fix does not broaden #724
resource-scoped authorization, modify permissions, or disclose installation
details or credentials to unauthorized callers.

**Approved visual reference:** Kubernetes provider's native connection
detail (`integrations/.../kubernetes/detail.html`). GitHub now reuses the
same `page_hero`, `_provider_detail_posture.html`,
`framed_workspace_tabs.html`, `integrationWorkspaceTabs`, and
`integrations/components/_workspace.html` section geometry. Tabs:

- **Configuration:** canonical identity, environment, GitHub installation
  ID, repository-selection scope, provider authority and current readiness.
  Private key PEM and webhook secret are never redisplayed.
- **Validation & Capabilities:** committed readiness, CSRF-protected
  **Run Full Validation** via the existing admitted JobExecution. It does
  not claim repository inventory has been committed.
- **Runtime & History:** existing most recent canonical JobExecution and
  signed webhook receipts. Empty webhook evidence remains a valid empty
  state when webhooks are disabled.
- **Inventory & Lifecycle:** existing committed-only, 15-second HTMX
  repository inventory with exact SHA, collection freshness and rows per
  page; **Sync Repositories** remains disabled until readiness is `ready`.
  Sync is still subject to worker registration, canonical job policy and
  resource-scoped admission; neither the GET nor this redesign triggers
  a sync.

The Hero **Review Validation** action selects the Validation tab without
inventing readiness. **Back to Registry** leads directly to the
GitHub Connection Registry, not the older intermediate UAT installation
list. Recent POST feedback initially selects the Validation or Inventory
tab depending on the operation. Existing CSRF validation and guards in
`uat_routes.py` are unchanged.

**Additional quality correction:** The user-provided djLint formatting
difference for GitHub registration `registration_actions.render` was
applied without changing test/save/proof semantics.

**Dev Container Human UAT:**
1. From Integrations → Source Control → Provider Registry click the
   registered GitHub connection's **Open**. It must open the correct
   GitHub installation detail and must not remain on the same domain.
   Non-authorized roles must not access the installation detail.
2. At 1440×900 and mobile widths in both themes, compare the GitHub
   Hero/Posture, tabs, spacing, status icons and compact responsive panels
   to the approved Kubernetes Manage Integration design.
3. Switch Configuration → Validation → Runtime → Inventory by mouse,
   keyboard and touch. The Review Validation Hero CTA should select the
   Validation tab.
4. Run Full Validation only with authorization and observe its actual
   canonical JobExecution status. Run Sync only after readiness becomes
   `ready` and existing dispatch policy allows it. Confirm one
   connection registration is not mislabeled as committed inventory.
5. Confirm repository inventory pagination/HTMX still works, no private
   PEM/webhook secret appears, and runtime jobs/deliveries correctly
   represent current committed evidence.

This is a holding-branch UAT workstream, not official Developer Check,
Full Admission, production release or approval. Keep issue OPEN until
executable quality checks and Human Acceptance are recorded.


## 2026-10-26 — #3246 follow-up: GitHub Configuration contract parity

The operator reviewed the merged GitHub four-tab Manage Integration screen
against the approved Kubernetes Configuration panel. Two Human UAT findings:

1. The GitHub Hero's **Committed Repository Grants** context line wrapped.
   Use the concise **Committed grants only** helper (single line at the
   1440px desktop UAT viewport). The **Unknown** metric remains unknown
   until collection and is not substituted with zero.
2. The GitHub Configuration card still used an isolated **Access &
   Authority** two-column layout, unlike Kubernetes **Connection
   Contract → Connection Evidence → Operational Context**. The page now
   follows that existing structure using the shared
   `integrations/components/_workspace.html` header and palette macros,
   `components/table_label.html` metadata label, semantic readiness
   indicator, and the **same**
   `integrations/components/_provider_operational_context.html`
   reusable macro used by Kubernetes. It has four compact identity cells
   (canonical identity, environment, GitHub App ID and installation ID),
   four provider-specific evidence cells (host, readiness, repository access
   scope and committed inventory authority), four governed lifecycle steps,
   and an explanatory footer. Identity and permissions remain GitHub-owned.
   There is no misleading security posture claim, new credential field,
   synthetic success or backend change.

**QA repair:** Operator attached exact Ruff formatter differences for
`kernel_contract.py` and `test_source_control_github_uat_scope.py`,
exact djLint differences for `uat_detail.html`, and a 53-PASS/1-FAIL
contract that incorrectly assumed single-quoted
`url_for('github_source.index', tab='registry')` when the Jinja template
uses double quotes. This follow-up applies Ruff's reported formatting and
matches the template's literal without changing the back-link destination.
It also adds an assertion for the shared Configuration contract and
Operational Context.

**Visual acceptance:** compare GitHub Configuration at 1440×900 and
mobile/desktop, light/dark, directly against Kubernetes Configuration.
The Hero helper must occupy one line. Connection Contract and Evidence
headers, metrics/evidence responsive grids, operational steps and footer
must use existing KAORI tokens, spacing and shared components. Verify
status remains **Validation Required** before Full Validation and
inventory remains **Not Observed / Unknown** before authorized Sync.
No further GitHub App change, secret display or real provider call is
required for this purely visual review.

## 2026-10-26 — #3246 GitHub permission guidance parity (Human UAT)

The GitHub installation **Configuration → Connection Contract → Operational Context**
now includes **Minimum Validation GitHub Permission Example**, reusing the accepted
Kubernetes modal composition and shared integrated workspace tab component.
The two modal tabs distinguish:

- **Baseline Validation Permissions:** repository `metadata: read` and
  `contents: read`, required by `readiness.py` for exact source revision
  readiness. GitHub installation selection governs which repositories are granted.
- **Optional Governance Permissions:** read-only `pull_requests`, `actions`,
  `checks`, `deployments` for specifically enabled capabilities, not mandatory
  for core connection readiness. Administrative, Secrets and write grants are
  deliberately absent; privileged operations need their own GitHub-side approval.

Both panels show a copyable GitHub App permission JSON example; the examples
are **not current observed permissions** and the copy action does not alter
GitHub, KAORI credentials, Full Validation or committed repository inventory.

The **Configure Connection** button links to GitHub's installed-app management
entrypoint `https://github.com/settings/installations` in a separate tab.
This is explicitly provider-side configuration, **not** an unimplemented
KAORI edit form. For organization-owned installations, navigate to GitHub
organization **Settings → GitHub Apps → Configure**. GitHub remains authoritative
for installation/repository grants; changes require renewed Full Validation
and separately authorized repository synchronization in KAORI. A first-party
KAORI edit/credential-rotation flow is **not implemented in this UAT scope**.

### Guided visual and interaction QA

1. In Dev Container, sign in as an active local super-admin with
   `integrations.manage`; navigate **Integrations → Source Control → GitHub →
   Connection Registry → Manage → Configuration**. Use a registered,
   non-production test installation. No live provider mutation is required.
2. Under **Operational Context**, inspect the new two-column minimum permission
   summary. Confirm footer **Configure Connection** is visible, aligned with the
   lifecycle caution and opens GitHub's installed-app settings in a new tab.
3. Click **Open Permission Examples**. Verify baseline tab default, accessible
   dialog title, responsive code scrolling, Copy Baseline JSON, Optional Governance
   Permissions tab, Copy Optional JSON, and Close/X/Escape/outside-to-close.
   Check focus return to the trigger. Do not grant scopes during visual QA.
4. Repeat at 1440×900 and 390×844 in light and dark modes, keyboard-only. Verify
   no content clipping, hidden controls, accidental form submissions or false
   indication of provider validation. Browser evidence remains **NOT RUN**
   until actual Dev Container execution.
5. Confirm Full Validation and Synchronize operations keep their existing separate
   CSRF-protected POSTs, and committed inventory remains Unknown until real
   synchronization. No token, PEM, webhook secret or installation credential
   may appear in page/JSON examples/screenshots.

Focused candidate checks (run on exact UAT SHA):

```bash
python -m ruff check tests/unit/test_source_control_github_uat_scope.py
python -m ruff format --check tests/unit/test_source_control_github_uat_scope.py
djlint --check app/templates/integrations/source_control/github/uat_detail.html app/templates/integrations/source_control/github/partials/_minimum_validation_permissions.html
python -m pytest -q -p no:cacheprovider tests/unit/test_source_control_github_uat_scope.py tests/ui/test_source_control_github_app_onboarding_contract.py tests/ui/test_source_control_integration_workspace_contract.py tests/contracts/integrations/test_provider_detail_lifecycle_parity_contract.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_sidebar_navigation_standard.py
```

**Authority:** #3246 (open), prior merged #3252. This is temporary holding-branch
UAT only. UI/browser and executable quality evidence plus Human Acceptance remain
pending; official Developer Check, Full Admission, `kaori/staging`, `main` and
release remain HOLD.


## 2026-10-26 — #3266 Connection Edit & concise permissions Human UAT

Operator's screenshots show long permission descriptions wrapping in the GitHub
modal; the reviewed GitHub Configure Connection CTA incorrectly opened GitHub.
This correction reuses the **Kubernetes Edit Connection** pattern and shared
`_provider_edit_hero.html`, returning to KAORI's own installation-scoped edit
page. Minimal modal descriptions and warning copy fit desktop single-line space,
while narrow layouts may wrap naturally without horizontal overflow.

**Edit authority and security:** The registered connection's canonical name,
environment, description and enabled status can be saved through a Flask-WTF
CSRF-protected POST, still requiring the existing `integrations.manage` and
local-super-admin UAT gate. GitHub App ID, Installation ID and account identity
are provider-owned, read-only binding identifiers. Shared encrypted App PEM and
webhook secret are neither displayed nor modified by this bounded edit; rekeying
a shared App affects multiple installations and needs separate rotation design
and UAT authority. Save emits a sanitized operational activity event.

**Readiness:** Name/description-only edits retain existing validated readiness.
Changing environment or enabled status clears stale Full Validation evidence
and returns readiness to `validation_required`; historical committed repository
and revision evidence is preserved. The operator must explicitly run Full
Validation again, then independently authorize repository synchronization.

**UAT sequence:** GitHub Registry → Manage → Configuration → Configure Connection
must open KAORI's Edit GitHub Connection screen. Verify prefilled canonical
name/environment/description/enable flag and read-only App/Installation/Account
IDs. Save a description-only change and confirm redirect, audit, and unchanged
readiness. Try a duplicate name and invalid environment; ensure no changes
commit. Change enabled/environment on an authorized disposable installation
and confirm Validation Required with no automatic provider mutation. Verify
CSRF and unauthorized direct GET/POST fail closed. Run local Ruff, djLint,
focused pytest, navigation verifiers and relevant Playwright light/dark/mobile
tests, record exact-SHA evidence, and await explicit Human Acceptance.

Earlier source guidance in this guide describing the external GitHub
installed-apps link is **superseded** by this new internal KAORI Edit route.
Official Developer Check, Full Admission, staging/main, release remain HOLD.


## 2026-10-26 — #3271 Protected GitHub App credential rotation (Dev Container UAT)

**Supersedes #3266's metadata-only edit limitation**: operators do not need
to delete/re-register an existing GitHub connection to replace a compromised
or rotated **GitHub App private key (PEM)** or **webhook secret**. The native App,
Installation and Account IDs remain immutable because they are GitHub-owned
source identities referenced by KAORI historical committed evidence. To connect
a different installation, register a distinct connection and retire/deactivate
the old one through its governed lifecycle; do not transplant repository history.

The **Edit GitHub Connection** screen uses the approved Kubernetes
`_provider_edit_hero.html` and existing GitHub **Test Connection → verified
short-lived proof → Save Changes** flow. The Hero caption is concise for
desktop and wraps safely for mobile. Existing App credentials are **never
rehydrated** into edit HTML; blank PEM / webhook secret fields mean retain the
existing encrypted values.

When replacement fields are populated, Test Connection runs an installation-
scoped authenticated GitHub App probe against the **same** bound App/Installation/
Account IDs and issues a requesting-user/form/secret-fingerprint-bound proof.
Saving requires that fresh proof and repeats the live GitHub installation check
before storing the encrypted replacement. If form fields change after testing,
the proof is invalidated. **Webhook secret validity cannot be verified via the
GitHub REST installation API**; Test Connection validates App/installation only.
Because a GitHub App credential can serve several SourceInstallations, rotating
either credential resets previous Full Validation/readiness of all connections
bound to that shared App; their existing committed repository grant and revision
evidence is retained as historical data, not silently re-assigned.

No registration webhook, secret, token, PEM or raw provider response is stored
in JobExecution, returned from GET, redisplayed on failed POST, or placed in
operational event metadata. Editing name/description alone stays offline and
retains readiness. Changing environment/enabled/credential returns impacted
connections to Validation Required.

### Dev Container UAT requirements

1. Pull the current `kaori/review/staging-uat` holding SHA and review
   **Source Control → GitHub → Connection Registry → Manage → Configuration →
   Configure Connection**. At 1440×900 check the one-line Hero subtitle;
   repeat at 390×844 and light/dark without forced nowrap.
2. Open existing disposable installation. Confirm App ID/Installation ID/Account
   ID read-only and both credential replacement fields blank, with no protected
   value rendered in HTML/DOM.
3. Metadata-only Save requires no GitHub network call and retains readiness.
   For key rotation, paste a valid GitHub App PEM for the *same App*, Test
   Connection, then Save Changes. Confirm audit, encrypted replacement and
   `validation_required` status; no source-grant history rewrite. Webhook
   secret-only replacement likewise requires Test and affects the shared App.
4. Negative tests: Save replacement without Test, stale/tampered/cross-user
   proof, test failed for mismatched installation or PEM, invalid webhook
   secret/length, unauthorized local identity, CSRF failure, and duplicate
   name all reject without modifying current protected credentials. Test first
   then change any field before Save must invalidate proof.
5. With two disposable installations referencing the same GitHub App credential,
   verify a rotation resets **both** readineses. Run Full Validation separately
   afterward. Repository synchronization is an independent approved operation.
6. Run existing Ruff/DjLint/pytest/navigation gates and browser accessibility
   checks against the exact merged SHA; record logs/screenshots and explicit
   Human Acceptance. Earlier operator QA at #3266: Ruff import FAIL,
   Ruff Format FAIL (4 files), djLint FAIL (edit template), focused pytest
   **46 passed**, integration/sidebar verifiers PASS on an earlier SHA only.

No official Developer Check, Full Admission, staging/main promotion or release
until the operator explicitly authorizes the next gate.


## 2026-10-26 — #3280 Governed GitHub Installation Replacement from Edit

**User feedback:** App ID, Installation ID and Account ID displayed read-only made changing
installation identity look like a destructive delete/recreate operation. KAORI now
provides **Edit GitHub Connection → Replace Installation**, preserving the
current integration and offering editable App/Installation/Account IDs on a
dedicated replacement form. The existing connection's IDs remain immutable:
they are committed-evidence identity anchors, and mutating them in-place would
relabel historical grants, jobs, source references, and webhook deliveries.

**Successor semantics:** Clicking Replace Installation opens the same provider
edit Hero/context pattern, with three editable provider-native IDs, a unique
successor connection name, and optional write-only PEM/webhook secret fields.
Test Replacement → short-lived, user/predecessor/bound-form signed proof →
Register Replacement. Save uses existing `save_tested_connection`, which
rechecks live GitHub identity and creates a **new** canonical
`IntegrationInstance` and `SourceInstallation` with readiness
`validation_required`, empty committed inventory, no automatic sync. It
retains the original installation, grants, revisions, logs, and audit records.
The user can test and later independently deactivate the predecessor. This
is an in-workspace successor operation, **not** in-place reassignment of its
historical identity, nor forced manual Delete + Register.

For the **same App ID** with a new installation, the existing protected
credential is reused on the server (blank PEM/webhook replacement fields).
For a **different App ID**, both new credentials are required and encrypted
under the new App identity. A new credential supplied for an existing App ID
must match the stored protected credential; rotate that shared credential
using the existing edit operation before registering another installation.
The existing same-native-installation identity cannot be duplicated.

**Security:** Existing `integrations.manage`, local super-admin UAT
admission and CSRF controls apply to both GET/POST. Provider calls happen only
on explicit Test/Save, not GET. Signed successor proof uses a distinct salt
and binds requesting user, predecessor installation, proposed native identity,
successor name, environment, and credential fingerprint; expires under the
existing registration-proof interval. Secret values must not appear in logs,
HTML on GET or failed POST, audit metadata, or JobExecution. Proof is not
a substitute for the save-time live recheck. Provider authorization stays
authoritative.

**UAT:** In an explicitly disposable GitHub App environment, inspect
Edit Connection → Replace Installation at desktop/mobile, light/dark and
keyboard. Verify native IDs are editable only in replacement context; test a
different Installation ID with same App credential; test a different App with
provided PEM/webhook. Reject unchanged App/Installation pair, duplicate name,
invalid App/account ID, proof from another user/predecessor, changed fields
after Test, invalid/missing proof and unauthorized/CSRF submissions.
Confirm old record still shows its prior repository evidence and status;
new connection is Validation Required/Not Observed and needs separate
Full Validation and repository synchronization. No automatic predecessor
retirement. Gather source-SHA audit and screenshots before Human Acceptance.

**Operator QA on older SHA:** Ruff Check PASS, djLint PASS, focused pytest
50 passed, navigation/sidebar PASS; Ruff Format failed 2 files:
`registration.py` and `test_source_control_github_uat_scope.py`.
Exact diff hunks are corrected in the successor work branch, but the final
merged SHA must be validated again before claiming PASS.

Official Developer Check, Full Admission, `kaori/staging`, `main`,
deployment and release remain HOLD.


## 2026-10-26 — #3297 Validation & Capabilities design parity (Human UAT)

**Authority:** the existing approved Alertmanager `Validation & Capabilities`
workspace is the visual/interaction reference, reusing shared components.
The GitHub Core Readiness + Validation Boundary-only layout is superseded by:
Full Validation header/action, Provider Readiness with metric/gate/evidence/next
action, Readiness Explanation, and a six-row Capability Registry.

**Evidence / semantics:** the UI is a committed-state projection of
`IntegrationInstance.metadata_json.github_validation`; it makes no GitHub
API calls during GET or capability filter paging. The six capability read
contracts are exactly those already defined in GitHub `readiness.py`.
`Permission Verified` means Full Validation observed granted read scopes,
**not** live provider health, a successful API probe for every optional
capability, or committed repository/revision inventory. Unknown/missing
Full Validation stays **Not Validated** and required gaps remain **not
assessed**, not zero. The required Metadata + Contents permissions are
separate from four optional scopes. Inventory synchronization remains an
authorized, independent operation.

**UI standard:** shared `_capability_readiness.html`,
`_readiness_explanation.html`, native `_record_detail_modal.html`,
`_provider_capability_detail.html`, table filter/loading/pagination and
record action components; default five rows, size options from KAORI
pagination standard, HTMX filter/partial update, empty state and
keyboard-accessible View More. Registry filter's unverified mode is
opt-in to the shared server-side registry function so other provider
views remain unchanged. The Full Validation POST preserves the existing
CSRF gate and canonical JobExecution admission.

### UAT
1. Pull holding branch; view **Source Control → GitHub → Manage →
   Validation & Capabilities** with an unvalidated UAT connection. Confirm
   permission verified=0, required gaps **Not Checked**, capability rows
   **Not Validated**, and never a provider-Ready claim or fake inventory.
2. Run Full Validation on an authorized disposable installation. Validate
   six capability states from committed snapshot; Required vs Optional,
   read-scope names, provider evidence/impact and View More. Actual
   provider mutation is **outside this UI-only PR**.
3. Search/filter by requirement and status; test 5/10/25/50 pagination,
   previous/next, Clear Filters, HX partial swap/loading, no-JS navigation,
   empty state and selected **Validation** tab persistence.
4. Compare with Alertmanager at desktop 1440x900 and mobile 390x844,
   light/dark, keyboard and native dialog focus/Escape. Reverify
   Full Validation CSRF POST and separate Sync Repositories.
5. Run Ruff, Ruff Format, djLint, focused pytest and integration/sidebar
   verification on the exact merged SHA. Preserve execution logs and visual
   evidence. CI PASS alone does not complete Human Acceptance.

**Gate state:** Human UAT pending; official Developer Check / Full Admission,
`kaori/staging`, `main` and release HOLD.


**Canonical validation loading:** The GitHub Full Validation header now also
reuses the existing validation worker's active-task snapshot, shared
loading/header, job status, 1.5s poller, record-scoped status access guard
and HTMX region replacement. The legacy non-HTMX POST redirect remains
supported; the new status GET requires local authorized UAT access and
matches `integration_type=source_control` and the exact canonical instance
before returning a result. The tab readiness badge is refreshed using the
shared OOB badge macro. No new worker/task/queue or provider GET on normal
workspace rendering was introduced.


## 2026-10-26 — #3306 Runtime & Inventory parity / review holding UAT

**UI authority:** reuse Kubernetes Runtime Health & Diagnostics and Inventory &
Lifecycle decision layout, Alertmanager shared Runtime Decision, and KAORI
shared connection header, table, pagination, status, loading and worker
poller. GitHub Full Validation header/boundary explanations are shortened,
without altering readiness semantics.

**Runtime & History:** Runtime Refresh is the existing admission-gated
`enqueue_github_app_job(operation='runtime_refresh')`; the same local
super-admin + `integrations.manage` + CSRF restrictions apply. A permitted,
record-scoped status poll returns only the current canonical instance's
JobExecution result; worker access and provider calls remain separate from
GET. Runtime health is not inferred from installation registration or
Full Validation. The Runtime Decision, current evidence, paginated/filtered
JobExecution history and signed webhook delivery receipts are distinct
evidence areas. Webhook receipts are transport evidence, not repository
collection, and secrets/payload hashes are not projected.

**Inventory & Lifecycle:** `read_installation_inventory` remains the
sole installation-authorized committed repository read projection. Its
`total=None` indicates *Unknown* when no committed complete generation
exists, distinct from a committed `total=0`. The decision shows freshness,
coverage, connection lifecycle context and provider evidence ownership.
Boundaries describe GitHub permission authority and preserved predecessor
history; they do NOT authorize deletion, move old evidence, or create a new
provider identity. Sync Repositories is separate and gated by Full
Validation. Registry uses KAORI shared table/page controls, default five,
standard 5/10/25/50 Rows and existing HTMX polling.

### Acceptance evidence to capture
1. Run Ruff Check, Ruff Format, djLint and scoped pytest on exact holding
   SHA. Prior **65 pytest passed** is older-SHA evidence. Format failures
   identified in the operator's previous QA logs need a new PASS.
2. Desktop 1440x900 / mobile 390x844, light/dark. Compare Header/Runtime
   Decision/Inventory & Lifecycle with Kubernetes and Alertmanager.
3. Runtime not observed vs completed Runtime Refresh; job/delivery empty,
   filter, pagination, active loader/status polling, forbidden access and
   CSRF handling. Cross-installation task snapshots must return 404.
4. Inventory Unknown vs committed zero vs committed nonzero, exact SHA,
   pagination, and freshness; refresh does not broaden installation scope
   or call GitHub directly.
5. Run authorised Full Validation, then Sync Repositories separately.
   Verify no unsolicited provider mutation, no automatic lifecycle
   deletion or successor migration. Human Visual Acceptance required.

No official Developer Check, Full Admission, staging/main promotion or
release until the operator accepts this holding UAT.


## 2026-10-26 — #3306 Human UAT follow-up (Toast, Help, Tabs, Registry)

- **Configuration feedback:** existing `record_operational_activity(..., queue_feedback=True)`
  remains authoritative and creates the standard dismissible operational
  success toast. The duplicate persistent `Connection Operation` callout
  is suppressed for `configuration_updated` and
  `configuration_revalidation_required`, while blocking/error callouts
  remain visible. No new toast runtime or direct provider change.
- **KAORI hover info:** Connection Contract, GitHub Full Validation and
  Repository Inventory & Lifecycle use the existing accessible
  `components/info_tip.html` popover. Shared connection header gains
  optional `title_extra` for additive reuse.
- **Evidence Boundary:** compact copy preserves GitHub as grants authority,
  KAORI as committed repository/revision evidence owner.
- **Runtime & History:** one server-owned compact `content_tabs.render_links`
  registry with Recent Jobs / Signed Webhook Deliveries; selected view via
  `?tab=runtime&runtime_view=jobs|deliveries` supports browser history and
  no-JS navigation. Both underlying server-backed HTMX table fragments
  retain their own filter, Clear Filters, 5-row default, Rows, pagination
  and loading. Scope/authorization remains installation-specific.
- **Inventory & Lifecycle:** committed Repository Registry is a separate,
  full-width `table_ui.block_classes` section after the decision card
  using existing table/pagination; never confuse Unknown with committed 0,
  or sync grants automatically.
- **Evidence pending:** run executable Ruff/djLint/pytest and desktop/mobile
  light/dark/keyboard/HTMX Visual QA on exact merge SHA. This is still
  temporary holding UAT, not Human Acceptance or official CI/CD admission.


## 2026-10-26 — #3306 KAORI title-level Guide and UAT QA regression

- Connection Contract, GitHub Full Validation and Repository Inventory & Lifecycle must use the **approved title-level Guide control** (`info_tip.render(..., placement='right', variant='guide')`), not the default inline circle-help/question-mark trigger. The component remains the canonical accessible popover for pointer, keyboard and touch. Do not introduce a competing hover style.
- Preserve connection save toast, separate authorized provider validation and inventory synchronization, and committed evidence authority. Runtime table parts retain explicit jobs/deliveries registry-view markers for UI contracts.
- Operator Dev Container evidence on previous merge SHA reported 2 failed and 66 passed: stale success-feedback quote assertion and missing runtime registry-view markers. Both source contracts are corrected for this UAT candidate. Formatter diagnostics (Ruff and djLint) require executable recheck on its exact merge SHA; no passing result is claimed.
