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
   existing manual `secrets_pki.vault_alerts.observe` job and inspect its
   committed result. The browser does not call the provider directly.
5. For the approved local operator UAT only, start/restart the existing
   Dev Container web process with `APP_ENV=development` and both
   `KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED=true` and
   `KAORI_VAULT_PROVIDER_CASE_OPERATOR_WEB_ENABLED=true`. A shell export
   alone does not change a running web process. Do not set these in shared
   or deployed environments. Remove them after the local review.
   Navigate to Intelligence → Alert Intelligence → Secrets & PKI →
   HashiCorp Vault → approved instance → Active, then select
   **Reconcile Cases (Local UAT)**. The action requires both independent
   exact instance grants and the four role permissions above. It only
   admits existing committed observations, never collects provider data
   or dispatches delivery. An empty first observation is unchanged, not
   recovered. Refresh an expired observation before retrying.
6. With fresh admitted firing, review, acknowledge, assign/unassign an
   eligible owner explicitly, then mark as mitigating as the assigned owner.
   Refresh the observation and admit again before its freshness deadline.
   Confirm stale/unknown source, revoked grant or unavailable owner controls
   fail closed. Check audit records with redacted evidence.

The Overview must show admitted cases, critical severity, fresh firing and
unknown separately; no records is not a provider health claim. Local
functional review is distinct from Developer Check, Full Admission and
Human Acceptance. The recovery and delivery implementation below is
conditional on independently provisioned real evidence; never simulate
successful provider recovery or transport acceptance.


## HV-12 — Signed recovery and explicit delivery local UAT (#5252 / #5253)

Code is available in the review workbench; all executable and browser
validation remains pending. Use the same isolated Dev Container, disposable
provider instances, and existing local-only opt-ins above. Do not create a
real notification destination or configure a production signer for this UAT.

1. **Recovery source prerequisite.** Identify the actual provider-owned rule
   evaluator's retained explicit resolution record for the exact Alertmanager
   occurrence. Establish fingerprint/startsAt continuity, source/binding
   identity and completeness. A GET response that omits an alert, elapsed
   endsAt or a silent source is not an authority. Provision the independently
   pinned provider exporter described in
   `app/secrets_pki/TELEMETRY_BINDING.md` in the read-only deployment mount
   `/run/kaori/vault-alert-authority`. Keep private signing keys outside
   KAORI; do not generate a synthetic recovery receipt. A trusted exporter
   has not yet been configured in this workbench.
2. Observe real firing, reconcile and acknowledge/mitigate in the case.
   Trigger a real recovery in the disposable source and have its authoritative
   exporter emit the signed exact receipt. Execute the existing observation
   job, then use **Admit Provider Recovery (Local UAT)** on the case if the
   action qualifies. Confirm source resolved and workflow verification
   pending, with separate source and operator evidence. No same-occurrence
   active/suppressed response or older resolution may be accepted.
3. Run another observation after verification started. A distinct newly issued signed provider receipt after verification started
   must qualify, then a different operator with independent exact
   read and decision scope may choose **Verify and Close (Local UAT)**.
   Review Resolved history and the redacted timeline. Reject same actor,
   stale generation, missing/tampered receipt, revoked scope and replay.
4. **Destination prerequisite.** Use a dedicated disposable Notification
   Channel configured only for Secrets & PKI / alert_ops.firing; validate
   it using canonical Test Delivery. The maker must also hold explicit
   integrations.manage. Create the candidate on the exact Vault Routing tab.
   The scoped table provides policy/channel IDs and exact UTC revision fields
   for independent approval, with no credentials or destination values. A distinct checker with normalized
   roles.manage/users.manage/integrations.manage and an approved exact read
   grant reviews the actual disposable destination outside KAORI and signs
   the exact case/binding/source/policy/channel revision and validity receipt.
   Mount its separate verification pin and receipt in the same fixed
   read-only authority directory; no private key in application containers.
5. With a fresh open firing case, select the exact Routing Candidate from
   the scoped selector. Use Review Approval (no network call), then only
   with explicit disposable-channel authorization select Send Approved Firing. Confirm the redacted journal and audit, and a single accepted
   notification at the approved destination. Attempt duplicate submission,
   changed channel/receipt, revoked grant and acknowledged/unknown source:
   no new transport. A crash or ambiguous failure is review-required, never
   automatically retried. Only a definitive Slack 429 with valid Retry-After
   permits a new signed approval and explicit retry of the same transport
   after its due time. Generic recovery excludes the manual-only scoped
   journal without rewriting its status or attempt count. An earlier skipped
   record qualifies for explicit retry only with matching definitive rejection
   audit, due time, attempt budget and a new independent receipt.
6. Review all views in light/dark/mobile and validate CSRF, permissions,
   independent approvals, source freshness, exact occurrence, PostgreSQL
   claim/lock concurrency and no leaked raw payloads or credentials. Record
   exact tested SHA and real provider evidence. Resolved notification,
   automatic repeats and provider-specific postmortem editing remain
   unqualified. Do not run official admission or deploy an RC until local
   validation and human approval are complete.


### Local authority mount and bounded readiness

For an approved disposable source/checker deployment, extend the existing
ignored `secrets/devcontainer/compose.host-overrides.yml` (merge with its
current mappings; do not replace unrelated configuration). The following is
a template only. Substitute the actual absolute host directory populated
by the independent authorities, not a repository directory or generated
sample receipt:

```yaml
services:
  workspace:
    volumes:
      - type: bind
        source: /absolute/path/to/approved-vault-alert-authority
        target: /run/kaori/vault-alert-authority
        read_only: true
        bind:
          create_host_path: false
  inventory-worker:
    volumes:
      - type: bind
        source: /absolute/path/to/approved-vault-alert-authority
        target: /run/kaori/vault-alert-authority
        read_only: true
        bind:
          create_host_path: false
```

Only public verification pins and independently signed receipts belong in
this directory. The directory and files must be root-owned, not group/world
writable; do not mount signing keys. Use the existing Dev Container
recreation procedure for changed mounts and preserve PostgreSQL volumes.
Verify the read-only mount in both services before opting into local
recovery. The stable correlation HMAC secret remains separately injected
only into the authorized inventory worker. Do not copy or print it.

The source snapshot now uses schema v2. A previously committed v1 snapshot
or a changed binding/source revision is intentionally unavailable until a
new observation is committed; no migration, manual database edit or reset
is required. Recovery history and closure counters are populated only from
qualified admitted records, and source conflicts are counted separately.

This template does not provision an exporter, signer, channel, key or
receipt. In the absence of those external authorities, review firing,
acknowledgement, ownership, mitigation, scoped routing candidates and
negative/blocked recovery and delivery states only. Do not claim successful
positive recovery or provider delivery based on code availability.


### Local delivery evidence: unconfirmed journal claims (#5253)

The Vault provider-origin Notification Delivery Ledger projects only a
canonical exact-case firing claim with matching audit. It displays **Sent**
only for a matching committed accepted outcome, **Failed** only for an
explicit audited rejection, and **Review Required** for a durable claim
without confirmed transport outcome (including a queued claim after a crash,
a worker-suppressed row, or an audited ambiguous outcome). A mismatched
outcome/status/rejection flag is **Not Qualified**, never reported as sent.
The ledger is a bounded redacted case projection, not proof of exactly-once
transport and not permission to retry an unconfirmed send.

When consolidated Dev Container checks are approved, exercise positive
accepted/rejected cases, no-audit crash after claim, skipped by generic
recovery, missing/out-of-order outcome audit, and altered rejection marker.
Compare the journal with canonical audit and independently approved
disposable provider receipt. No automatic recovery or retry is authorized
by this display change; **actual outbound tests remain HOLD** until signed
destination approval and local human acceptance.


### Unified operator review checklist (#5229 / #5230 / #5253)

- Overview shows committed open, critical, unknown and verification-pending
  evidence for the selected authorized scope. Without a scope, counts are
  unavailable; the seven-provider implementation matrix remains visible.
- Choose domain, provider and instance; context changes clear prior tab-local
  filters. Active and Resolved filters remain separate. Resolved supports
  verification pending, closed, committed recovery and source conflict.
- Use Active Alerts to review an occurrence and take only the currently
  qualified action. Use Resolved to review recovery and independent closure.
- Delivery review selects a single exact policy/channel candidate. No claim
  in the current journal and audit is distinct from unavailable evidence.
  Already accepted, unconfirmed, contradictory or not-yet-due outcomes
  do not offer another transport action. Due rejection remains conditional
  on the existing server-side requalification, not the selector or label.
- Exercise malformed and cross-instance candidate submissions, duplicate
  claim, stale receipt, role denial, generic recovery exclusion, no-JS GET
  fallback, pagination, light/dark and responsive review. Record actual
  provider receipt, audit and test output before acceptance.


### Final scoped review regression checks

- Revoke the selected instance grant while the Active, Resolved or Routing
  registry is open; trigger a filter or pagination request. The complete
  page must replace the previous case summary and controls with a blocked
  state rather than leave stale rows in the browser.
- Record an independently qualified definitive rejection. Only its original
  maker may see the original policy/channel candidate after the due time;
  other makers and other destinations cannot retry it. Recheck current
  approval and transport authority on the server as before.
- Verify the Active filter has a non-JavaScript submit fallback and that
  successful recovery/closure returns to the resolved context.
