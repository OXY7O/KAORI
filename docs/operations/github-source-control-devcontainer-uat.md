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
