# Source Control — canonical identity and GitHub lifecycle

Authority: [#559](https://github.com/OXY7O/KAORI/issues/559), [#958](https://github.com/OXY7O/KAORI/issues/958), implementation [#2740](https://github.com/OXY7O/KAORI/issues/2740).

## Current admitted staging baseline (2026-11-02)

The canonical provider matrix on `kaori/staging` declares `Source Control → GitHub` as **`available`**, after the reviewed [#3399](https://github.com/OXY7O/KAORI/pull/3399) staging integration. SC-01 identities, the GitHub App SC-02 registration/validation boundary, and SC-03 committed installation-scoped repository inventory are represented in the staged source. Full Admission and staging deployment have passed for the accepted source; this does **not** by itself prove live GitHub App installation UAT, broader production authorization, or hosted Human UAT acceptance.

- GitHub remains the external source of truth. KAORI records normalized, generation-fenced inventory and authoritative JobExecution evidence; standard operational views should use committed KAORI state.
- Installation-specific UAT operations are restricted to an active **local database Super Admin** through `require_uat_access()`, alongside route-level `integrations.manage` where applicable. **#724** resource-scoped access for broader use is not superseded by the provider matrix's `available` lifecycle.
- Signed webhook HTTP ingress and the maintenance inbox consumer retain **independent default-off gates**: `SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=false` and `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED=false`. A committed webhook receipt is not a completed repository reconciliation.
- The [existing GitHub App Dev Container UAT runbook](../../docs/operations/github-source-control-devcontainer-uat.md) records earlier review-workbench procedures and verification cases; use the current staging SHA and appropriate environment for new evidence. Historical review-branch HOLD statements in that record are not the current staging lifecycle authority.

## Historical SC-01 foundation checkpoint

The original SC-01 increment reserved the **Source Control** capability in the canonical integration taxonomy, and initially registered **GitHub** in the provider matrix as **planned**, not Available. The shared Integrations domain route used the existing workspace; no provider adapter/instance was registered and no live GitHub access, tokens, inventory or Product UI were claimed at that checkpoint.

`identity.py` defines immutable, host-qualified provider-native keys for App installation, account, repository, exact revision and branch/tag reference. It does **not** represent a GitHub App installation as an account, infer repository access from a name, interpret branch/tag as immutable source, or provide authorization by itself.

## Historical SC-01 next steps

- Review the new inert persisted identities against the live schema and verify migrations/foreign keys with Dev Container tests.
- Preserve committed relationship history, effective dates, observation/freshness, and explicit access-lost vs deleted semantics.
- Verify existing migrations, identity service, RBAC/#724, definition and navigation contracts before marking SC-01 complete.

SC-02 (#2741) owns provider authentication/readiness; SC-03 (#2742) owns authorized collection, snapshot publication and reconciliation. At the SC-01 checkpoint, activation of GitHub in the provider matrix remained gated on adapter admission and security/validation evidence; the current staging state is recorded above.


## Persisted identity contract (SC-01 increment)

The migration `20261023_sc_identity` adds *inert* source records with no seeded
connection, GitHub tokens, live API reads, or provider availability claims.

| Model | Authority |
| --- | --- |
| `SourceAccount` | Host-qualified GitHub native account, independent of mutable login |
| `SourceInstallation` | One IntegrationInstance to one App installation grant; optional linked account |
| `SourceRepository` | Host-qualified native repository ID, independent of name/owner and installation |
| `SourceRepositoryGrant` | Installation-to-repository access, effective-dated independently of provider presence |
| `SourceRevision` | Sparse repository-scoped exact SHA; no git history mirror |
| `SourceReference` / `SourceReferenceTransition` | Current branch/tag targets and independently observed ref transitions |

The database uniquely keys accounts, repository IDs, installations and
repository-scoped source revisions. A partial unique index limits each
installation/repository pair to one currently open access grant; historical
records remain retained. A repository may be visible through multiple
installations without duplicating its identity. `provider_presence`,
`archived`, `grant_status` and `access_status` are independent; data
absence, scope change and provider unavailability are not deletion proof.

SC-02 must never persist App private keys or short-lived installation tokens in
these tables. Only the canonical credential boundary can own such protected
material. SC-03 must enforce same-host/same-repository references, verified
source identity, generation-safe writes, observations and effective-dated
transition semantics in its worker/services; raw CRUD writes are not
authorization or observation evidence.

**UI contract:** reuse the existing Integration domain page and its shared
Hero, cards, tables, modals, pagination, HTMX and semantic state components.
No GitHub-specific page or duplicated Violet styles are introduced by SC-01.
At the SC-01-only checkpoint, the provider remained `planned`; this historical statement does not describe the current staging matrix.


## Historical SC-03 candidate — committed GitHub Repository Inventory (#2742)

This section preserves the original **issue-scoped SC-03 candidate** and its
Draft PR context; it is not a current statement that the staged provider is
`planned`. Staged registration, jobs and committed repository inventory were
integrated separately through the approved review snapshot. Live provider
readiness still requires actual provider and security evidence, not merely
a successful code admission.

- `repository_discovery.py` asks GitHub.com for the installation's exact
  granted repository pages (20 per page, bounded to 200 pages). It verifies
  installation App/account/scope before and after collection; token scope,
  native owner identity, stable `total_count`, unique native IDs and
  exhaustive pagination. A rate limit, malformed page, revoked installation,
  unexpected scope, token expiry or bound exceeded must **fail closed** with
  no committed inventory changes.
- `SourceRepositoryCollectionState` provides per-installation fencing:
  reserve a generation and commit that reservation before network reads.
  A later reservation makes an older scan stale; only the current complete
  generation can commit. Collection state, scope, prior successful coverage,
  last-committed timestamp and count remain distinct.
- `repository_commit.py` updates SourceAccount/SourceRepository by their
  immutable provider+host+native IDs, preserving rename continuity and
  optional previously observed values. Access is separately effective-dated
  per installation. Only a complete grant inventory may close a granted
  relationship into `access_lost`. A repository is **never labeled deleted**
  because its selected installation grant disappeared; other installations
  retain their own access evidence.
- `repository_sync.py` is a candidate service callable by a future worker:
  reserve -> collect -> publish, or record a sanitized degraded generation.
  It does not register a new Celery task or dispatch a job. The approved
  worker must reuse canonical KAORI JobExecution and SC-02 installation
  identity, implementing scheduling, retries, recovery and webhook-triggered
  reconciliation only after security/CI/UAT admission.
- `repository_inventory.py` is a **committed-state-only** page projection,
  with KAORI pagination 5/10/25/50. It requires an installation ID that
  has already passed #724 resource-scoped authorization; it has no route
  until that constraint is enforced. If no complete generation was committed,
  count and coverage are UNKNOWN rather than zero.
- This increment does not implement a Git clone, file blobs, PR/Actions,
  committed default-branch SHA, ref transition collection, branch/tag
  history, full repository timeline, global Source Control inventory route,
  provider kernel activation, new UI primitives, or production GitHub calls.
  Exact source revision/ref evidence requires independently verified
  GitHub API reads before being committed.

**Migration:** `20261023_sc_repo_collection`, downstream of
`20261023_sc_webhook_delivery` on the stacked review branch. It adds
`default_branch`, `visibility`, and a new collection-state table; no
provider identities or repository rows are seeded. Run existing KAORI
`verify_migration_graph.py`, migration upgrade/downgrade, `ruff`,
`pyright`, and focused `pytest` through Developer Check in the
Dev Container. Evidence must include cross-organization/installation
negative tests and live All/Selected grant reconciliation. No official
staging/main CI is authorized yet.

### Exact default-branch revision evidence (SC-03 incremental)

- `default_branch.collect_default_branch_revision` requires a committed, currently `granted` installation-to-repository relationship. It uses GitHub App installation tokens with `metadata:read` and `contents:read`; the latter is required for GitHub's Get a branch endpoint.
- `GitHubAppClient.default_branch_tip` checks GET `/repos/{owner}/{repo}` before and after the allowlisted GET `/repos/{owner}/{repo}/branches/{branch}` call to prove the mutable owner/name resolves to the same native repository ID. Redirects, network failures, token expiry and ambiguous refs fail closed.
- `reference_commit.publish_default_branch_revision` independently rechecks current grants, canonical repository native ID and default branch; SourceRevision uses Repository + exact 40-hex SHA, SourceReference is mutable, and SourceReferenceTransition retains observed pointer movements. Out-of-order observation cannot revert a later tip.
- The installation-scoped read projection now includes `exact_default_branch_sha` and `revision_observed_at`, only where the matching committed current default-branch pointer is known. Missing evidence stays Unknown; an old branch's revision is not misrepresented as the current branch SHA.

This does not mirror Git history, collect branch/tag catalogs or file blobs, guarantee the observed tip is still live, or activate provider runtime. Future UI must show the observation time alongside SHA. Resource-scope authority #724 remains a blocker for public inventory routes.

Additional focused Dev Container checks (authored, not executed):

```bash
pytest -q --tb=short tests/unit/test_source_control_github_default_branch.py tests/unit/test_source_control_github_default_branch_collection.py tests/unit/test_source_control_github_reference_commit.py tests/unit/test_source_control_repository_inventory_read.py
```

No extra schema migration is required for refs: this increment reuses SC-01 SourceRevision, SourceReference and SourceReferenceTransition. Keep existing migration graph, ruff, pyright, pytest and Visual QA gates.

### SC-03 — Registered JobExecution and signed-webhook post-commit handoff (candidate)

- `source_control.repository.sync` is in KAORI's existing registered Jobs catalog. It uses the current `inventory` queue, `JobPolicy`, `JobExecution`, progress/cancel/recovery facilities, and shared Jobs Configuration UI. Its initial policy is **disabled**, and manual dispatch is blocked until #724 resource-scoped authorization is admitted.
- Only an approved `source_control` provider, enabled canonical GitHub App installation, matching account/credential, and a `Ready` Full Validation result can produce targets. Workloads are capped at 25 installation IDs. The worker rechecks eligibility before each metadata-only provider scan; no PEM, token or raw webhook enters task args or job payload.
- The existing `CELERY.imports` and `task_routes` declare the worker on `inventory`. The canonical dispatcher requires a live worker advertising the exact task before enqueueing; nothing is dispatched by importing this module or defining the job.
- Authenticated webhook transport is first staged and committed in the existing delivery ledger. `webhook_handoff.dispatch_committed_delivery` then claims it in a transaction and commits the claim **before** requesting an installation-scoped canonical job. On success, `dispatched_job_execution_id` links the queued JobExecution, not an invented source event or completed sync.
- A failure before accepted dispatch becomes bounded `retry_pending` / `requires_review`; a possible post-enqueue persistence failure or abandoned claim becomes `dispatch_uncertain` for review, **not an automatic duplicate job**. The preexisting current installation grant is still checked; a targeted webhook hint only triggers an independently authorized installation-wide refresh.
- Webhook ingestion and outbox consumption are **not exposed as public routes** or scheduled yet. The handoff helper alone is not operational end-to-end webhook delivery. Completion status must be reconciled from canonical JobExecution, and the separately authorized ingress/consumer lifecycle must be admitted before enabling it.
- Migration `20261023_sc_webhook_job_link` extends the existing webhook ledger with an optional FK to `job_executions`. It follows `20261023_sc_repo_collection`; no data is seeded and no worker runs during upgrade.
- A mid-scan revoked installation, API outage, failed DB publication, canceled job or invalid generation must not erase the last committed repository scope. The failure marker is written only for the still-owned pending generation.

**Dev Container checks still required (not executed):** `python scripts/verify_migration_graph.py`, `python scripts/verify_definition_registry.py`, `ruff`, `djlint`, `pyright`, focused `pytest` for `test_source_control_repository_registered_job.py`, `test_source_control_repository_worker_contract.py`, `test_source_control_github_webhook_handoff.py`, plus PostgreSQL migration upgrade/downgrade, worker preflight, negative RBAC test and visual light/dark/responsive review.

**Historical release boundary:** SC-01 #2740 → SC-02 #2741 → SC-03 #2742 were stacked Draft PRs; those individual heads did not authorize admission. The subsequent reviewed source was separately admitted into `kaori/staging` through #3399. Do not infer real live GitHub App UAT, hosted Human Acceptance or `main` promotion from either source admission or the earlier Draft PRs.

### SC-03 — Signed ingress and JobExecution completion recovery (candidate)

SC-03 now includes **two independent, default-off admission switches**:

- `SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=false`: `/integrations/source-control/github/webhook` responds **404** before reading the body or querying an installation. The Source Control provider matrix must also be admitted before the endpoint accepts a POST. Rate limiting is applied; the 256 KiB raw-body bound, JSON content type, authenticated HMAC-SHA256, UUID replay key and exact installation scope are enforced before a delivery is committed. A successful request returns **202** only for committed transport receipt, **not** reconciliation completion. The route never dispatches a job or trusts payload repository metadata.
- `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED=false`: no Source Control webhook maintenance beat entry is added while disabled; its Celery task is registered only on the existing `maintenance` queue. An explicitly enabled task still declines processing if GitHub is `planned` on the executing branch; the independent ingress/consumer flags remain required on the current `available` staging provider.

`webhook_recovery.recover_webhook_inbox` examines up to 25 eligible committed delivery rows per pass, respecting due retry/backoff and only polling queued jobs once their canonical JobExecution is terminal or missing. Failed preclaim verification gets bounded retry then `requires_review`; abandoned `dispatching` becomes `dispatch_uncertain` and is **not automatically resent**. A broker/persistence exception of unknown dispatch acceptance also becomes `dispatch_uncertain`, not optimistic re-enqueue.

`webhook_completion.reconcile_delivery_completion` checks canonical Source Control `JobExecution` job type, operation, integration and **exact installation scope** before recording `reconciled_success`, `reconciled_partial`, `reconciled_failure` or `reconciled_canceled`. An active job stays `queued` in the transport ledger. Missing, expired or cross-installation execution becomes `requires_review`. These labels describe transport-to-job correlation, not raw webhook proof of GitHub data.

**Remaining provider-specific UAT:** verify two-App/installation isolation, live HMAC/replay/rate-limit negatives, worker restart/registration, crash recovery, #724 resource-scope decisions, Visual QA, and explicit human acceptance on the exact running source. The admitted staging source already has CI gate evidence, which must not be mistaken for those live checks. **Do not enable either webhook switch without an explicit UAT plan and approval.**

