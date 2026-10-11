# Capsule Release — guarded handoff and recovery source boundary (#1229)

Status: **DevContainer source-review slice; provider execution NOT admitted**.
Parent #991; prerequisite source #1227 and #1228. Neither merge nor committed
successor acceptance source is actual X.509 consent or provider authorization.
Target integration: `kaori/review/staging-uat` only. No developer check,
pytest, Ruff, pyright, CI/CD, DAST, live API UAT, promotion or deployment until
a separate explicit instruction.

## Authoritative inventory and transfer model

Capsule Tenant `capsule.clastix.io/v1beta2` is **cluster scoped** and continues
to own Tenant spec, quota, limitRange, owner, RBAC and future namespace policy.
The approved SHA-bound Release plan carries exact Tenant CR UID/resourceVersion
and full canonical spec digest plus each governed Namespace UID/resourceVersion.
It is not permission to PATCH Capsule Tenant spec or replay Native handoff.

The review-only `capsule_handoff_contract.py` implements:

- Pure bounded scope validation: exactly one approved Capsule Tenant CR, between
  one and thirty Namespace records, unique kind/name, exact UID/RV, authority,
  ownership classification and canonical Capsule spec SHA-256.
- A no-write Capsule CR preservation assertion: exact CR identity, exact
  spec SHA, no unreviewed KAORI CR markers. A source-marked CR with an
  unverified KAORI owner is **blocked** rather than stripped or re-labeled.
- A Namespace-only conditional JSON Patch plan: `test` UID, resourceVersion
  and complete original labels; `remove` only the known KAORI label keys;
  `add` the independently verified successor `app.kubernetes.io/managed-by`
  value. Capsule membership labels and all foreign labels, annotations, spec,
  quota, ownerReferences, finalizers and workloads remain untouched.
- Fail-closed foreign/mixed ownership, unknown `kaori.io/*` control markers,
  ambiguous Capsule membership, unsupported scope kinds, invalid owner values,
  missing identity and provider drift. A Namespace without a trusted Capsule
  membership label is not eligible for metadata transfer.

`capsule_handoff_dry_run.py` has **no route or background execution**. An
explicit caller can supply provider clients to preview the Namespace-only
conditional patch with Kubernetes `dryRun=All`; it then re-reads the live
Namespace and Capsule CR to compare identity, spec and retained state. Its
receipt is always `preview_observed_coverage_incomplete`, with
`dry_run_complete=false` and `provider_handoff_verified=false`. Even with
the supplementary read-only inventory described below, this is **not** an
admitted end-to-end provider handoff dry-run. No caller may interpret the
helper result as sufficient handoff proof.

`capsule_handoff_recovery.py` classifies exact Namespace baseline/read-back
into `pending_provider_transfer`, `provider_markers_transferred` or
fail-closed drift/partial ambiguity; its bounded aggregate reports
`provider_handoff_not_started`, `partial_handoff_recovery_required` or
`provider_markers_transferred_consent_unverified`. All recovery results have
`auto_retry_authorized=false`, `resume_authorized=false`,
`provider_handoff_verified=false`, `release_authorized=false`.

## Read-only related resource inventory — follow-up source slice

The existing committed Capsule preflight now calls
`capsule_handoff_related_inventory.observe_capsule_related_inventory` only
after it has correlated its exact governed Namespace records. For each
Namespace, the observer reads complete **bounded** Kubernetes lists:

- `ResourceQuota` and `LimitRange` from the Core API;
- `RoleBinding` from Kubernetes RBAC API;
- Each authoritative LIST resourceVersion, bounded count and every object's
  UID/resourceVersion, origin class, SHA-256 policy digest and SHA-256 retained
  metadata digest; never raw RBAC subjects, quota specs or authentication data.

Records are classified as `capsule_provider`, `foreign_preserved`,
`kaori_correlated`, `ambiguous_kaori` or `unattributed`.
Unknown and conflicting ownerReferences, foreign controller claims, unknown
KAORI markers, residual KAORI quota/limit controls or Access Grant RoleBindings,
incomplete LIST/pagination, duplicated scope, malformed spec and unbounded
inventory create **blocking evidence**, not silent adoption.

The committed result is placed in `capsule_related_inventory` for Capsule
only (Native evidence remains unchanged). The deterministic SHA-256 of scoped
objects **and LIST revisions** is bound into the existing Capsule Tenant
handoff component as `capsule_related_resources_sha256`; its existing
`handoff_fingerprint` now detects drift without changing route or database
schema. An incomplete read never emits a trusted resource digest.

**Remaining hard stop:** Kubernetes namespaced lists do not prove
cluster-scoped GlobalResourceQuota variants, the exact Capsule CR-to-generated
RoleBinding lineage, or the complete independent successor acceptance/execution
contract. When actual Capsule handoff is required, preflight explicitly
retains a non-allowlisted blocker until those controls are proven. The
legacy observation-only Release path is not granted a new executor.
The preview remains `dry_run_complete=false`. No provider write is introduced.

## Cluster-scoped quota and Capsule RBAC intent lineage — follow-up

`capsule_handoff_authority_inventory.py` adds **read-only, bounded**
observation for `globalresourcequotas.capsule.clastix.io` using the served
`v1beta2` API (with a `v1beta1` fallback only after 404). The observer binds
the full cluster LIST resourceVersion, each CR UID/resourceVersion, SHA-256
canonical spec and metadata, and source API version. It never clones or
updates quota. Missing CRD, partial/paginated/oversized LISTs, malformed
specs or unsupported tenant selector expressions fail closed. Foreign quota
objects are fingerprinted without claiming their management.

Capsule Tenant `spec.rules[].permissions.bindings` now has a **candidate**
lineage comparison against effective KAORI-correlated RoleBindings. The
comparison accepts only explicit Namespace-name selectors, unique bounded
scopes, exact ClusterRole reference and canonical subject identity. Its
committed receipt contains opaque SHA digests and counts, **not** subject
names, authentication material or raw role policies.
`additionalRoleBindings` with KAORI grant markers cannot be admitted as
an unbounded successor handoff. Mismatched effective RoleBindings, residual
KAORI access grants, unknown selectors and duplicated claims block.
Matching content is only `contract_correlated`; it does **not** prove
which controller created a RoleBinding or that the successor accepted it.

Both complete observations are committed under the existing Capsule
`capsule_related_inventory` evidence and SHA-bound into the same Capsule
handoff fingerprint via `capsule_shared_quota_sha256` and
`capsule_rbac_lineage_sha256`. The prior namespaced inventory digest remains
unchanged, and Native/legacy observation-only Release paths remain separate.
The existing non-allowlisted Release blocker remains until full provider
authority/transition evidence is available.

No route, provider write, persisted dry-run admission, executor,
Release transition or automatic recovery is enabled by this source slice.
Neither successful intent matching nor an unchanged fingerprint is consent.
Additional cluster-scoped Capsule GlobalTenantResource/resource-pool variants
remain subject to explicit version/capability admission rather than
being silently interpreted as a global quota.

## Admission evidence and recovery worklist — source-only follow-up

`capsule_handoff_admission.py` is a **pure, non-executable** evaluator of
the current Capsule Release plan hash, exact provider fingerprint,
independent approval, accepted X.509 successor, matching authenticated
SelfSubjectReview/SAR evidence, actor identity, zero active dependency counts,
fresh authoritative preflight and scoped CR/Namespace/Quota/RBAC evidence.
A record must be independently reloaded and reverified by a future guarded
service; a caller-supplied mapping is never accepted as operational proof.

The evaluator recomputes the namespaced ResourceQuota/LimitRange/RoleBinding
inventory digest and checks the committed Capsule CR component digests and
provider LIST coverage. It also binds the authenticated provider credential,
principal groups and exact SAR scope to the independently accepted actor.
A stale plan, duplicate/missing list, changed object, expired consent,
new RBAC subject, unmatched X.509 identity, missing preflight or forged
controller-origin boolean produces blocking reason codes **without sensitive
principal or credential values**.

`capsule_handoff_worklist.py` derives a deterministic **operator review
worklist** for Capsule Tenant CR preservation, Namespace ownership markers,
namespaced quota/limit/RBAC objects and GlobalResourceQuota. Every object is
classified as provider-preserved, candidate metadata review or operator
investigation. It recomputes source LIST + global quota digests instead of
trusting a hash field supplied by a caller. No raw provider spec, RBAC
subjects, live patch bodies or credentials are included. The SHA-256 worklist
fingerprint, counts and unresolved reasons are part of the pure assessment,
not a persisted provider execution receipt.

**Deliberate hard stop:** `rbac_controller_origin_unverified` and
`resource_specific_handoff_worklist_not_admitted` are mandatory blockers.
`dry_run_admitted=false`, `provider_execution_admitted=false`,
`auto_retry_authorized=false` and `release_authorized=false` are invariant,
including when all supplied preconditions match. No route, scheduler,
DB execution audit, live dry-run, PATCH, retry or finalizer was enabled.
Future actual controller-provenance proof must be a separately security-reviewed
provider authority contract, not a managedFields claim, label, or matching hash.

## Append-only attempt and no-retry recovery state — source-only contract

`capsule_handoff_attempt_state.py` models a **single attempt**, but does not
issue a Kubernetes request, create AuditEvents, or provide an executor.
It validates a narrow v1 event envelope bound to the exact approved plan
SHA-256, generation/cluster, provider fingerprint, deterministic source worklist
SHA-256, one canonical attempt UUID, accepted actor ID, strictly increasing
sequence/timestamps, and the prior event's SHA-256. Receipts contain only
counts, an opaque optional read-back digest, event type, and invariant
`provider_handoff_verified=false`/`release_authorized=false`. Unknown
fields (including accidental credentials or provider objects) are rejected.

| Event | Permitted follow-up | Source-only projection |
| --- | --- | --- |
| No event | None automatically | `no_attempt_observed_not_authorized` |
| `started` | `partial` or `readback_candidate` | `started_outcome_unknown_recovery_required` |
| `partial` | Independent `recovery_reviewed` | `partial_handoff_recovery_required` |
| `readback_candidate` | Independent `recovery_reviewed` | `readback_claim_requires_independent_provider_verification` |
| `recovery_reviewed` | No new start/retry | `manual_review_recorded_no_retry_granted` |

The source model strictly forbids a `provider_handoff_verified` event and
never converts an asserted all-transferred count into Released. A `started`
record with no final provider acknowledgement is **unknown outcome**, not
proof of no write. A manually reviewed partial/read-back claim is still
non-retryable without a new externally governed plan and explicit recovery
authorization. It requires a different human reviewer identity from the
attempt actor, but cannot verify that person's entitlement by itself.

Event SHA chaining is **not** tamper-proof evidence until anchored in a
trusted, append-only AuditEvent stream. The future operational executor
must independently enforce row locks, once-only attempt identity,
committed `started` evidence *before* first PATCH, strong provider read-back
and definitive partial/unknown receipts even on HTTP timeout, interrupted
process or database-write failure. It must check current actor, plan,
successor, Kubernetes TLS, X.509 SSR/SAR and resource origins immediately
before every permitted mutation. This projection does none of those
operations, has no route and never provides an execution capability.

## AuditEvent envelopes and candidate provider read-back — source-only boundary

`capsule_handoff_audit_envelope.py` validates supplied **chronological**
`AuditEvent` rows (not a database query or writer). Each record must have
the dedicated Capsule execution target, correct Tenant, strictly increasing
row ID and timestamp, matching actor, exact event action/type, and validated
`capsule-handoff-attempt/v1` checksum chain. An incomplete, duplicated,
malformed, reordered or wrongly attributed envelope fails closed.
These source checks **do not** establish database append-only guarantees,
audit-stream completeness, SQL durability, or authentic Kubernetes execution:
those require independently enforced operational controls.

`capsule_handoff_readback_evidence.py` compares separately acquired
Capsule Tenant CR, bounded Namespace baselines, all namespaced
ResourceQuota/LimitRange/RoleBinding LISTs and cluster-scoped
GlobalResourceQuota records against the exact original approved source.
It recomputes provider LIST digests and enforces each kind/Namespace's
unique list scope, resource counts, identity, UID and resourceVersion.
It checks provider spec, preserved ownership/finalizer/annotation digests
for KAORI Namespace handoff baselines. Any missing Namespace/baseline/LIST,
wrong kind, stale digest, changed global quota, provider CR/spec drift
or foreign constraint change is rejected or flagged for recovery.

The read-back candidate counts **all** KAORI transfer worklist objects,
including residual ResourceQuota/LimitRange/RoleBinding ownership, never
only Namespaces. Candidate metadata transfer is classified separately
from untouched provider-owned resources. An unchanged KAORI-related control
is still only *pending*; a changed one without separately admitted
resource-specific handoff remains unverified.

`inspect_capsule_audit_readback_link` correlates the recorded
`readback_candidate` SHA, worklist, plan and every transfer counter with
this observation. An exact match produces
`readback_claim_correlated_unverified`, not provider verification.
A partial/unknown operation, a matching checksum, or a manually reviewed
claim **never** authorizes retry or Released.

**Hard trust boundary:** no GitHub source merge, test fixture, audit-event
mapping or caller-supplied Kubernetes response is authenticated evidence of
a live handoff. A future guarded, explicitly consented executor must use
fresh TLS-validated Kubernetes clients, exact SAR permissions, independent
read-back after each permitted mutation, trustworthy append-only persistence,
and human recovery for incomplete operations. This slice introduces no
endpoint, scheduler, persistence, dry-run invocation or live PATCH; all
`provider_handoff_verified`, `readback_authoritative_verified`,
`auto_retry_authorized`, and `release_authorized` values remain false.

## Committed AuditEvent scan and persistence/recovery boundary — source only

`capsule_handoff_persistence_review.py` adds a read-only access path to
the existing SQL `audit_events` table. It fetches **all Capsule execution
records for one Tenant**, ascending by AuditEvent ID, with a fixed
`max_attempt_events + 1` bound to reject overlong attempts instead of silently trimming records.
The inspected records must match the canonical actor, event action, target,
attempt UUID, plan SHA, worklist and hash chain. Rows for prior plans are
**not** filtered away just to make a newer attempt appear empty. A START
without outcome is a recovery-required operation, not permission to retry.

The same module also reviews *proposed* next event envelopes against
committed history without executing an INSERT. `append_authorized=false`
and `trusted_audit_persistence_verified=false` are permanent outputs of
this source-only helper; it does not run SQL writes, lock rows, or grant a
Kubernetes operation. A valid event checksum establishes data consistency
within the supplied snapshot, **not** database immutability, durable
commit, independent human consent, or chronological stream completeness.

`capsule_handoff_persisted_recovery.py` correlates that read-only
history with an optional `readback_candidate` receipt and returns a
non-executable recovery docket. A previously started operation without a
definitive outcome is quarantined. A partial operation requires a fresh,
independent human recovery decision. An exact recorded read-back SHA is
still merely `readback_correlated_but_unverified`; it is not fresh
authenticated Kubernetes read-back and cannot authorize Released.

### Required storage/executor remediation before any live handoff

The shared `AuditEvent` model has an ordinary mutable JSON column and no
Capsule-specific database-enforced insert-only property or uniqueness
constraint. This must be treated as an **open blocking design gap**, not a
PASS inferred from source-only row validation.

A future independently reviewed implementation needs:

- A database-enforced **write-once, non-deletable** Capsule execution ledger
  or a comparably protected append-only event store; immutable attempt
  identity, unique `(tenant_id, plan_sha, attempt_id, sequence)`, and
  explicit unauthorized update/delete rejection.
- A Tenant-scoped transactional lock/fencing strategy, historical-attempt
  scan and once-only START commitment **durably acknowledged before** any
  Kubernetes write. A failed or uncertain commit must stop execution.
- A new freshness/authority decision just before each operation, including
  exact actor, independent plan approval, accepted successor, authenticated
  Kubernetes TLS/X.509 SelfSubjectReview/SAR, source fingerprints,
  provider-owned constraints and explicit resource-specific transfer scope.
- Per-resource conditional metadata-only patch, immediate authoritative
  provider read-back and separately committed partial/verified evidence.
  Timeouts, database errors, process crashes, conflicting controller writes,
  untracked history or uncertain outcomes remain human-recovery blockers;
  never retry automatically.
- Restoration/backup and retention protections for the ledger itself, plus
  testable audit guarantees across the actual database engine and deployment.
  SQL-model-level rules alone are insufficient to prove disaster durability.

None of these missing storage and live-operation guarantees is enabled by
this slice; no DB migration or AuditEvent writer is introduced. #1229
remains OPEN and #1230/#1231 blocked. All test, CI/CD and real provider
operations continue to be held pending explicit authorization.

## Capsule write-once event ledger — migration source only

`app/models/capsule_handoff_ledger.py` and
`migrations/versions/20261011_capsule_handoff_write_once_ledger.py`
define a **dedicated** `capsule_handoff_ledger_events` relation, separate
from the generic mutable `audit_events` table. The new model records only
the canonical attempt envelope, exact Tenant/cluster/generation and
plan/worklist SHA, indexed actor/sequence/event hash, and safe event JSON.
No Kubernetes subject, provider credential or raw resource spec belongs in
the ledger.

The migration is based on `20261009_tenant_released`. It is **authored,
not applied**. It supports PostgreSQL and SQLite explicitly, and refuses
other SQL dialects until their immutability controls are reviewed.
Both dialects enforce bounded event progression (START, one outcome,
optional independent recovery review) and unique Tenant sequence/digest.
Insert guards prevent missing predecessors, parallel/new attempts,
actor mismatch, different provider scope, and event chronology drift.
PostgreSQL uses a Tenant row lock to serialize inserts, and guards
UPDATE, DELETE **and TRUNCATE**. SQLite uses transaction-serialized
predecessor checks and UPDATE/DELETE triggers. Downgrade is forbidden
when events exist.

**Conservative irreversible fence:** only one attempt history is permitted
per Tenant. A future sanctioned restart cannot delete ledger evidence,
reuse attempt sequence or silently reset history. It requires a separately
approved recovery protocol and additive schema extension, not a bypass.

`capsule_handoff_ledger_review.py` provides a bounded read-only query and
compares each persisted indexed column with the canonical event payload
and its original checksum/state chain. It also detects missing START,
duplicate sequence, out-of-order records and changed plan/worklist.
It **never** calls INSERT, UPDATE, DELETE, SQL commit or any Kubernetes API.

### Admission still blocked

A source migration is not proof of installed database triggers, correct SQL
role privileges, WAL/fsync settings, backups or tamper resistance against
database administrators. The target database engine has not been verified
by an executed migration test. A future accepted execution service must
prove the write-once schema installed on the actual engine, restrict DB
role privileges, and ensure atomic persisted START acknowledgement plus
fencing and fresh Kubernetes authority before the first provider mutation.

The new ledger is currently **not used as an execution writer**. Its reader
reports `db_write_once_triggers_verified=false`,
`transactional_start_commit_verified=false`,
`append_authorized=false`, `provider_handoff_verified=false` and
`release_authorized=false`. Generic `AuditEvent` reader remains
observation-only; no legacy Native implementation is changed. The
next work item remains an explicitly reviewed **transactional writer and
live provider executor**, with authoritative Capsule controller lineage,
individual resource handoff and independent human consent, not an
automatic promotion of this source merge. All gates remain HOLD.

## Transactional START writer — source-staged, permanently disabled under HOLD

`capsule_handoff_start_writer.py` implements the next review slice:
`build_capsule_start_candidate` is a **pure** event builder which
recomputes the canonical plan hash and component fingerprint, the exact
Namespace/quota/RBAC worklist SHA, and the original bounded transfer count.
The event contains an attempt UUID, accepted actor ID, canonical START time,
zero observations, zero provider writes, no credentials or raw Kubernetes
policy and a chained SHA-256 digest. It must pass the existing attempt
state projection before a future writer can consume it.

`commit_capsule_start_staged` is intentionally **not registered or callable
for production handoff**. A source constant
`_CAPSULE_START_WRITER_ENABLED = False` rejects every call **before** opening
a database session, querying actor credentials or writing an event. No
environment flag, request body or user confirmation can change this.
Even a separate code modification removing that source gate would still
encounter the existing immutable Capsule admission decision:
`provider_execution_admitted=false` and `dry_run_admitted=false`
until controller provenance and resource-specific metadata authority are
independently implemented and reviewed.

The staged SQL path is for architectural review only. It specifies an
isolated PostgreSQL transaction, Tenant `SELECT ... FOR UPDATE`, current
adopted/Ready Capsule lifecycle check, full legacy-attempt and immutable
ledger scan, reloading of current committed plan/approval/successor consent
under the Tenant lock, and a second check of exact actor and provider scope.
It also requires **separate explicit operator confirmation**, not just an
accepted successor receipt. Only after future authorization could an
INSERT of the canonical START envelope happen; SQL constraint validation
(`flush`) alone is **not** a committed barrier. The transaction must
commit before a separate ledger read-back; no Kubernetes operation belongs
inside this writer, and its return value must never authorize provider
PATCH, retry or Released.

Before a hypothetical START INSERT, PostgreSQL inspection requires all
four enabled database ledger triggers (insert guard and update/delete/
truncate deny), normal replication role, `fsync=on`, synchronous commit,
and a dedicated **INSERT-only** (for mutations) application role which is
neither superuser nor table owner/owner-role member and cannot UPDATE,
DELETE or TRUNCATE the ledger. These checks are defensive source gates,
**not** proof of backup durability, immutable DBA-level history, approved
migration status or real provider authority. SQLite schema remains
inspectable and reviewable but is **not admitted as this distributed
transactional writer backend**.

### Required before operator authorization

1. Obtain explicit approval to execute the schema migration and database
   verification in the intended DevContainer/UAT environment; check
   PostgreSQL trigger behavior, concurrent START fencing, safe downgrade
   refusal, privilege isolation, WAL durability and backup/recovery.
2. Independently validate Capsule controller-generated RoleBinding origins,
   the entire affected resource set, per-resource transfer consent, fresh
   TLS X.509 SelfSubjectReview/SAR and guarded dryRun=All.
3. Security-review a separate source change to activate only a fully
   admitted START transaction, then verify durable commit before **any**
   eligible Kubernetes PATCH. Validate partial/timeouts/crashes and an
   authoritative post-write provider read-back with no automatic retry.
4. Keep #1229 OPEN, #1230/#1231 BLOCKED, and all CI/CD, tests, migration,
   provider operations and Release actions HOLD until individually authorized.

## Required before completing #1229

1. Build on the SHA-bound Namespace and cluster-scoped
   GlobalResourceQuota observations: prove the actual Capsule controller
   origin of generated RoleBindings, authorize any other served shared-quota
   variants explicitly, complete exact KAORI allocation/access transfer
   worklist and corresponding authoritative post-transfer read-back.
   Never relabel provider-owned objects. Residual KAORI-owned ResourceQuota,
   LimitRange or RoleBinding remains blocked until its exact metadata-only
   transfer is separately admitted.
2. Bind a committed dry-run receipt to the *current* independently approved
   plan SHA, provider fingerprint, live zero-dependency preflight, exact actor,
   accepted successor and fresh registered X.509 SelfSubjectReview/SAR with
   validated Kubernetes TLS. Revalidate immediately before each potential
   provider operation.
3. Add a separately confirmed guarded **live executor**, not available on
   ordinary GET, with an append-only `started` AuditEvent before any PATCH,
   per-object conditional mutation, definitive provider read-back, and
   `partial_handoff_recovery_required` on timeout/conflict/crash. Do not
   retry unknown outcomes automatically; require a new explicit human recovery
   decision and proof of exact original scope.
4. Expose intentional operator review/confirmation UI only after implementation
   and security review; use existing CSRF, HTMX, RBAC and Violet patterns. Do
   not overload Native executor, Native finalizer, or Release Step 4.
5. Author provider API mock regressions and UAT matrix for changed/reused RV,
   UID replacement, missing permissions/TLS/X.509, partial patch, retained
   quota/LimitRange/foreign RoleBindings/owners, full spec drift, concurrent
   reconciliation, restart and stale consent. Execute them only after the
   gate hold is explicitly lifted.

## Current operating boundary

`kaori-demo` is **NOT Released**. Three release handoff blockers remain
operational; no Capsule provider handoff or independent human acceptance has
been executed by this source change. #1230 verified finalizer and #1231
controlled provider UAT remain blocked. Source inspection is not gate PASS.

No new backend endpoint, database migration, Kubernetes mutation, provider
execution, Released lifecycle state or automatic retry is introduced here.
