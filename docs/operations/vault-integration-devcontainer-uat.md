# KAORI — Secrets Management Integration / HashiCorp Vault Design UAT

**Authority:** UI parity issue #3384; existing Vault HV-01 #2585, HV-14 #2855,
provider-first registration #3106, shared integration heading #3215, Secrets &
PKI independently guarded workspaces. The current approved
`docs/design/KAORI_INTEGRATIONS_LOCK_V1.md` and
`KAORI_INTEGRATIONS_LOCK_V1_1.md` remain normative.

**Target:** temporary `kaori/review/staging-uat`; official Developer Check,
Full Admission, `kaori/staging`, main, deployment and release all **HOLD**.

## Scope and architecture boundary

The UI is refactored using existing KAORI shared components; no new provider
adapter, background job, Secret/PKI collector, ACL, credential policy, migration
or provider mutating operation has been introduced.

- **Provider landing**: shared Hero, Overview, existing coverage boundaries,
  canonical Connection Registry table, server-side Search Connection,
  Environment and Validation filters, disabled/plaintext-free semantic status,
  automatically applied HTMX filters with GET/no-JS fallback, Clear Filters,
  Rows default 5 (5/10/25/50), and numeric pagination. Headline KPIs still
  represent the **unfiltered** canonical connection registry.
- **Configuration**: shared provider connection contract with read-only HTTPS
  origin, trust, AppRole, namespace, encrypted SecretID explanation,
  provider authority, and Configure Connection action.
- **Validation & Capabilities**: shared title/Guide header, Capability
  Readiness component, committed API capability presentation and CSRF-protected
  Full Validation action; no fake KV v2, PKI, or Runtime qualification.
- **Runtime & History**: shared Runtime Decision using the **latest committed**
  independent observation (not the current history page), protected runtime
  refresh, full-table runtime history with default 5 rows and numeric paging.
  'unhealthy' is blocked; no history is 'Not Observed', not Healthy.
- **Inventory & Lifecycle**: KV v2 metadata, public PKI issuer and opted-in
  stored certificate evidence remain **independent committed sources** with
  qualified coverage and timestamp boundaries. No Secret value, private key,
  raw AppRole token or credential in HTML.
- **Registration/Edit**: preserve two-stage Test Connection proof, exact-form
  binding and expiry, CSRF, HTTPS allowed origins, encrypted SecretID and
  existing form field validation. Reuse existing action button, Info Tip and
  operational callout rather than inventing a new test/submit interaction.
- **Access boundary**: the separate Operational Evidence navigation still
  requires `secrets_pki.view`; certificate analytics additionally requires
  `analytics.view`. Integration management alone never grants sensitive
  Secret-detail visibility. Vault owns values/leases/ACLs; KAORI owns
  committed metadata, orchestration, correlation and audit.

No Delete Connection action was added: Vault deletion lifecycle guardrails
must be independently approved/implemented before surfacing a destructive CTA.

## Dev Container evidence matrix

| Case | Expected behavior | Evidence | State |
| --- | --- | --- | --- |
| VLT-UI-01 | Provider Hero / Coverage / Registry match Violet Integration baseline | Light/dark screenshots, shared section positions | PENDING |
| VLT-UI-02 | Connection search, environment, validation filters query all committed instances, reset page | Filter URLs, row count, registry DB read-back | PENDING |
| VLT-UI-03 | Rows 5/10/25/50, numeric pagination, Clear Filters, zero-match and no-JS GET fallback | Browser and screenshot/trace | PENDING |
| VLT-UI-04 | Connection Contract shows only safe identity/auth/TLS data; edit action is present | HTML + encrypted-field leak check | PENDING |
| VLT-UI-05 | Full Validation action, capability state and permission boundaries remain independent | JobExecution and committed readiness + browser | PENDING |
| VLT-UI-06 | Runtime decision and history report committed latest observation, including page 2 | DB observation/timestamp, runtime page screenshot | PENDING |
| VLT-UI-07 | KV v2, public issuer, stored PKI evidence distinguish Not Collected/partial/stale/zero | Committed observation fixtures, rendered states | PENDING |
| VLT-UI-08 | Registration/edit do not leak SecretID, token, private keys or bypass proof validation | Negative Flask/provider sandbox, sanitized audit | PENDING |
| VLT-UI-09 | `integrations.manage` does not grant Secrets & PKI workspaces; analytics is separately guarded | Viewer/manager HTTP 403 and link visibility | PENDING |
| VLT-UI-10 | Responsive 6 viewports, light/dark, keyboard tabs, labels, Guide, empty/loading/toast/error | Playwright screenshots and trace | PENDING |

These are a **human UAT checklist**, not executed Gherkin/pytest scenario IDs.
Record exact tested `git rev-parse HEAD`, `git status --short`, user role,
safe Vault test scope, selected provider/mount fixture, timestamp, screenshots,
actual worker/job IDs, committed DB read-back, remediation issue and operator
decision. Never paste SecretID, PEM, raw Vault tokens or Secret payloads.

## Focused checks for the candidate

```bash
git fetch origin
git switch kaori/review/staging-uat
git merge --ff-only origin/kaori/review/staging-uat
git rev-parse HEAD
git status --short

ruff check \
  app/integrations/secrets_management/secrets_pki/providers/vault/application/routes.py \
  tests/contracts/integrations/test_vault_provider_workspace_contract.py
ruff format --check \
  app/integrations/secrets_management/secrets_pki/providers/vault/application/routes.py \
  tests/contracts/integrations/test_vault_provider_workspace_contract.py
djlint --check app/templates/integrations/secrets_management/vault/*.html \
  app/templates/integrations/secrets_management/vault/partials/*.html
python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_vault_provider_workspace_contract.py \
  tests/contracts/integrations/test_vault_operational_navigation.py \
  tests/contracts/integrations/test_vault_sidebar_navigation.py
python scripts/verify_integrations_final_lock.py
python scripts/verify_ui_reuse.py
python scripts/verify_ui_style.py
```

**Evidence boundary:** executable checks, page rendering, browser Visual QA
and real Vault sandbox UAT are NOT RUN when this document is authored. Prior
Source Control results (Ruff/djLint PASS and 78 pytest PASS) apply to that
capability only and cannot establish Vault UAT or acceptance.

## 2026-10-26 — QA feedback after first Vault UI parity merge

**Operator supplied a Dev Container log**, but did not include an exact
`git rev-parse HEAD` in the paste. Accordingly results below belong to
the tested working tree only; they cannot be attributed to a later SHA.

| Check | Operator-observed result | Disposition |
| --- | --- | --- |
| Ruff Check | FAIL — two I001 import blocks (Vault routes, Vault workspace contract) | Sorted on #3384 follow-up branch; exact-HEAD rerun required |
| Ruff Format | FAIL — same two Python files | Applied report-driven line wrapping/quotes; exact-HEAD rerun required |
| djLint | FAIL — seven Vault templates | Applied all seven exact formatter diffs from the supplied log; exact-HEAD rerun required |
| Focused pytest | 21 PASS / 1 FAIL | Prior test expected sidebar children without Source Control; now aligns with approved current sidebar |
| Integrations Final Lock | ERROR — IndexError on missing `capability_metadata` | Vault now passes profile metadata into the existing shared Capability Readiness contract |
| UI Reuse | PASS — 0 inline debt | Existing evidence only; rerun on exact HEAD |
| UI Style | FAIL — 16 violations across Access, Notifications, Kubernetes, Intelligence, Settings, Secrets & PKI | External cross-domain findings; **not** waived or fixed by Vault-only follow-up |

The failing sidebar assertion did not indicate a missing or duplicated
Secrets Management navigation entry; it only omitted the subsequently approved
Source Control sibling from its literal expected order. No navigation catalog
or RBAC behavior was changed. Existing Vault UI should not be modified merely
to satisfy obsolete assertions.

The shared Integration verifier's `capability_metadata` expectation is
preserved, not disabled. Vault identifies the AppRole profile only when
Full Validation is ready, and shows No Committed Validation otherwise.

No changes to the Vault provider adapter, Secrets data plane, SecretID,
PKI/KV v2 collector, permissions, migrations or production API were made.

**Outstanding human acceptance:** rerun all focused commands in the prior
section at the exact current holding SHA, then test safe Flask rendering,
light/dark, mobile, forms, filter/pagination, independent committed evidence,
RBAC and toast/error states. The external UI Style findings remain a
separate global gate; don't claim Full Admission PASS based on the scoped
Vault rerun alone.


## HV-12 — Local provider AlertCase review (#5229)

Use the review workbench only. Do not run a broad GitHub admission or deploy an
RC during this checkpoint. Use an isolated Dev Container database and approved
disposable Vault/Alertmanager pair; do not point a fleet observation at a local
database containing real provider connections.

1. Sync `kaori/review/staging-uat` with a clean worktree. If the local
   database is behind, follow the guarded Dev Container PostgreSQL migration
   runbook; never reset a volume or migrate using the runtime identity.
2. Register and validate the disposable Vault and Alertmanager using the
   canonical integration workspaces. Approve the exact Vault alert binding
   (`vault_instance=<canonical instance ID>`), then check the committed
   binding validation and worker readiness. The existing Vault Alert Source
   Observation job is manual-only, defaults disabled and selects the eligible
   local fleet. Its stable HMAC key belongs only to the authorized inventory
   worker; never print, rotate ad hoc, commit or put it in JobExecution.
3. In Access, ensure the operator has an active normalized role with
   `secrets_pki.view`, `intelligence.view`,
   `intelligence.decisions.create` and `secrets_pki.sync` for admission.
   Exact instance read and decision policies are independent. Existing backend
   request/approval commands in `app.access.scoped_grants` are the authority;
   only the approved independent administrators may create/approve grants.
   Use bounded validity and a separate approver. No direct policy SQL inserts,
   implicit Super Admin permits or automatic grant activation.
4. After local review of that scope and explicit operator approval, run the
   existing manual `secrets_pki.vault_alerts.observe` job, and inspect its
   committed result. No direct provider call from the UI. The internal
   admission command is a separate manual action; it does not collect data or
   dispatch notifications. In the isolated workspace shell, use the explicit
   local opt-in:

   ```bash
   APP_ENV=development KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED=true flask --app app shell
   ```

   ```python
   from app.intelligence.alert_intelligence.vault_provider_admission import admit_vault_provider_cases
   # Supply the approved disposable binding ID and the actual authorized actor ID.
   # Do not substitute a different user's ID or create a grant to bypass review.
   result = admit_vault_provider_cases(binding_id=binding_id, actor_user_id=actor_id)
   print(result)
   ```

   The placeholders must be assigned from the approved local test inventory.
   The result exposes only status/created/refreshed. An empty first observation
   is unchanged, not recovered. Refresh an expired observation before retrying.
5. Review Intelligence → Alert Intelligence → Secrets & PKI → HashiCorp Vault →
   approved instance → Overview / Active. The default read UI is available
   with the exact read grant. Only for the approved local operator-action UAT,
   start/restart the existing local web process with both
   `KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED=true` and
   `KAORI_VAULT_PROVIDER_CASE_OPERATOR_WEB_ENABLED=true` in its environment.
   A shell export alone does not change a running web process. Do not set these
   in shared or deployed environments. Remove them after the local review.
6. With fresh admitted firing, review, acknowledge, assign/unassign an
   eligible owner explicitly, then mark as mitigating as the assigned owner.
   Refresh the observation and admit again before its freshness deadline.
   Confirm stale/unknown source, revoked grant or unavailable owner controls
   fail closed. Check audit records with redacted evidence.

The Overview must show admitted cases, critical severity, fresh firing and
unknown separately; no records is not a provider health claim. Recovery,
closure and actual notification delivery remain unqualified; they must not
be simulated as successful. Local functional review is distinct from
Developer Check, Full Admission and Human Acceptance.
