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
