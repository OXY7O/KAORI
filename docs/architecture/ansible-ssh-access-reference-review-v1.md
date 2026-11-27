# Ansible SSH Access References — Review-Only Contract v1

**Authority:** #556 Infrastructure Automation, #4796 Ansible execution, #5155/5161 canonical host inventory, #5162 SSH/credential admission, #714 Secrets & PKI, #4799 dedicated worker. Downstream immutable Plan #5163/#4800 and non-production mutation #4801 remain separately authorized.

## Ownership and first implementation

The first #5162 source slice in `app/infrastructure_automation/host_access_reference.py` is a **pure read-only reference classifier**, not credential/SSH admission. It interprets only a canonical active non-production Ansible `IntegrationInstance` with source-checked immutable Git pin, an immutable EE digest reference, one KAORI host asset identity, existing `SecretIdentity` + `SecretProviderRepresentation` metadata, and an opaque public host-key digest. Secret values remain owned by the external provider; KAORI owns only normalized evidence/correlation.

It refuses cross-provider, wrong secret identity, unknown/revoked representation, missing version, unknown host/invalid scope/source/EE or absent host-key reference. A structurally valid record is labeled `references_recorded`, **never** `ready_for_execution`. Merely providing a Vault representation ID or host-key digest does not prove key usability, SSH host-key trust, access scope, network reachability, privilege escalation or an admitted automation worker. The function does not accept worker-provided approval flags.

The operator-facing committed summary is only a deterministic fingerprint, generic reason/status, and two Boolean `*_reference_recorded` indicators. It always exposes `ssh_trust_verified=false`, `privileged_identity_verified=false`, `execution_authorized=false`; it does not serialize host IDs, IPs, secret identities, Vault paths or raw key material. The fingerprint is **not a signature or authorization token**. A changed source, EE, secret version or host-key reference changes the fingerprint and invalidates any prior review correlation.

## Security separation / remaining children

1. #5161: after asset model/namespace admission, read only permission-scoped Compute/VM/Bare-Metal host identity from approved KAORI persistence. Do not use Kubernetes `NodeInventory` as pre-provision SSH inventory.
2. #5162 follow-up: use existing Secrets & PKI scope permissions and authoritative provider secret metadata, not user-submitted model instances. Require actual approved secret role/type, current secret version, host↔secret binding and secret-provider verification.
3. #4799/#5066: add isolated worker trust, SSH known-host identity, remote host-key verification and sudo/privilege proof from a non-production disposable target under exact Git SHA and signed EE digest. No SSH from normal GET/Flask and no credential values in Celery/JobExecution.
4. #5163/#4800: persist only a canonical immutable, time-bounded Plan/JobExecution and validate freshness/worker admission/source/secret/inventory at every execution boundary.
5. #4801: independent maker/checker + change window and target lock, Ansible Runner/Kubespray native execution, independent Kubernetes API readback. Production enablement and upgrades remain HOLD.

## Validations

Ruff/check-format, focused pytest, Pyright, Developer Check, Full Admission and Security/DAST on exact head; independent review and staged human non-production UAT separately. No schema migration, route, UI action, secret write, arbitrary Ansible inventory, authorization broadening, live SSH or cluster mutation is delivered by this small foundational slice.

## Governed candidate recording (#5162)

The internal create-only service `record_host_access_reference` takes the authenticated server-side actor and opaque selection intent (connection, host UUID, expected host revision, exact approved scope UUID, canonical Secret UUID, expected version and public-key digest candidate). It requires explicit existing role permissions, reuses the canonical #724 exact Vault mount evaluator with its policy locks, reads a bounded complete matching collection generation, pins the selected current available version and stages mandatory Activity Audit in the same transaction as the binding. Denials, stale selection, duplicate existing binding, and expected audit/commit boundary errors roll back with a generic non-enumerating denial. Any unexpected programming failure also rolls back before propagating internally; a future HTTP boundary must never expose raw exceptions. No broad exception handler or debt-baseline exception is introduced. No replacement is enabled. The actor's approved metadata-read scope does not grant credential-use authority. No new HTTP route or selector is exposed until the remaining credential type, target ownership and trust authority are admitted. Actual SSH, worker attestation and execution remain blocked. SQLite timestamp handling follows the existing committed metadata convention; PostgreSQL transaction/concurrency validation and human UAT are separate.

### Transaction regression coverage

In addition to isolated orchestration tests, the persisted fixture exercises the actual canonical scope evaluator, committed host/Secret reads, binding storage and Activity Audit on a real SQLite database. It checks authorized create, duplicate denial, foreign actor, unknown Secret, version drift, revoked policy, incomplete generation, host drift and rollback after both records have been staged and flushed. PostgreSQL concurrency/locking verification remains separate; SQLite does not demonstrate row-lock behavior.

## Credential-use authorization — accepted direction, concrete scope proposal (#5183/#5184)

The architecture direction was accepted by donibawono in [#5183](https://github.com/OXY7O/KAORI/issues/5183#issuecomment-7126946218). This increment records the concrete contract for Access review; it does not register or grant a permission. The source-controlled Access catalog currently defines `secrets_pki.view` and `secrets_pki.sync`, neither of which grants material use. `jobs.execute` is not a credential-use grant.

- **Proposed permission key (pending Access review):** `secrets_pki.use_automation_credential`. Purpose: allow only a qualified internal read-only automation workflow to consume one provider-owned, typed SSH credential version, never reveal/export it to a human. No default role or implicit super-admin/ownership/team grant. The canonical Access registry and delegation/seed contract remain authoritative.
- **Proposed exact scope extension:** retain the canonical ScopeAccessPolicy principal/permission and revision lifecycle. The existing `instance` and `vault_mount` scopes remain metadata-only; neither is inherited into material use. A new exact automation credential-use selector must bind the initiating user, Ansible connection, canonical host asset and inventory assignment (including role and host revision), Vault connection/namespace/mount, Secret identity/representation/current version, approved operation/profile and immutable source revision. Review the storage and constraint extension under #724 before introducing it; no resource IDs in permission keys, wildcard selectors, parallel grant store or caller-provided approval flag.
- **Grant versus operation:** an independently approved, currently effective policy revision is necessary but not sufficient. Require separately approved target/operation intent, typed provider credential/version authority, independent host-key trust (#5185), signed EE and worker identity (#5186). Re-evaluate active initiating actor, latest policy revision, current host/binding/provider version and operation immediately before provider use and dispatch. Retry/replay may not reuse an old allowed decision as a permit. Mandatory sanitized audit and rollback/deny on unavailable evidence apply.
- **Secret boundary:** provider-owned typed credential and narrowly scoped access must be qualified separately; generic KV metadata does not establish SSH type or permission to read material. Never persist private material in the binding, broker, JobExecution, logs or UI. No provider retrieval or worker admission is implemented here.
- **Invalidation:** actor deactivation, grant expiry/revocation, changed assignment/role/endpoint, credential rotation/deletion, source change or trust invalidation blocks new use and invalidates correlated preflight/Plan evidence.

The existing scoped-grant regression suite now explicitly tests that an active approved metadata-read grant cannot authorize `secrets_pki.sync`, `jobs.execute`, or the proposed credential-use key through the metadata evaluator. This test does not establish the future material-use grant. Independent review and the existing gates must pass before further implementation; actual credential material delivery and remote read-only UAT remain separate.

### Canonical permission registration increment (#5184)

Following independent review of #5187 and its staging merge, the canonical Access catalog registers `secrets_pki.use_automation_credential` with explicit dependencies on `secrets_pki.view`, `inventory.view` and `jobs.execute`. No protected default role receives it, and no other permission implies it. Catalog registration is not an active grant; normal explicit seed/convergence and Access delegation boundaries remain unchanged. The existing metadata-only evaluator rejects this key even for an actor with an explicit role mapping and an independently approved metadata grant. The exact resource scope extension, typed provider authority, operation approval, independent trust and worker admission remain separately gated. No material retrieval or remote execution path is introduced.

### Proposed provider-owned exact-version typed proof (#5184)

Vault KV v2 metadata inventory remains metadata-only. It does not prove the credential schema, and generic custom metadata, a path naming convention or a caller-supplied type flag is not immutable version authority. The proposed first credential class is a dedicated SSH private-key credential (`kaori.vault.kv2.ssh_private_key.v1`); the provider-side credential owner must validate the actual schema and exact version before issuing evidence, with no material transferred to KAORI for this qualification. A password, generic token or privilege assertion is not interchangeable with this class. Concrete provider-side validation, SSH identity binding and issuance procedure need independent review before enabling an issuer or a reader.

The proposed offline signature contract binds the exact Vault integration instance, namespace, approved mount, path SHA-256 digest, positive version and provider creation timestamp to a fixed type schema and signed UTC issuance/expiry window (maximum 24 hours, no future issuance). The canonical statement is sorted compact ASCII JSON using the documented fixed fields, signed with Ed25519. The provider-side issuer must retain exclusive signing authority; a future independently governed issuer registry must pin the verification key to the exact provider/scope and validate key lifecycle, custody, rotation and revocation. Do not accept an arbitrary public key supplied with a statement, infer trust from signature validity, or reuse one source's issuer for another without explicit approval. No signer/issuer registry, trust anchor, attestation persistence or provider material validation is implemented by this increment.

The offline Vault adapter helper `verify_credential_version_statement` reconstructs the proposed canonical statement from its exact selector and verifies its signature and validity window using an independently supplied public key. Positive verification is only a cryptographic statement check. A future governed caller must resolve canonical current committed records, prove issuer authority and provider-side version type, verify lifecycle/collection freshness, bind evidence to the independently approved grant and operation, re-evaluate before any material use, and deny on revocation or unavailable evidence. Worker-side exact version schema validation and ephemeral private material delivery remain separate #5186 gates. No provider requests, credential values, SSH, activation, or dispatch are introduced here. The proposed contract requires independent review and real provider evidence before it becomes operational authority.

### Proposed exact-scope credential issuer registry persistence (#5184)

The Secrets & PKI model `SecretCredentialIssuerRevision` retains one intended append-only revision history per exact integration instance, namespace and mount, with an explicit admitted provider key (`vault` or `openbao`). Each revision records Ed25519 raw public-key hex and SHA-256 key digest, independently qualified external deployment reference and custody evidence reference (both SHA-256 hex), effective validity window, requester, independent approver and recording actor. Active shape requires distinct requester/approver, matching approver/recording actor and a valid approval time. A revoked revision can retain expired history. No wildcard mount, backfill, seed or active issuer is created; downgrade refuses to discard recorded history.

Storage shape alone is not a trust anchor. The existing Vault health projection does not commit an authoritative deployment identity; the new OpenBao integration must independently qualify its own identity. The merged registry schema (#5199) is provider-neutral under #5200/#5204, not a second OpenBao-specific store. A provider key must match the canonical integration instance; the unique scope revision deliberately cannot fork on a changed provider key. A future governed source-owner workflow must independently establish deployment identity (not merely endpoint or local instance ID), prove key custody and actual provider-side credential schema validation, qualify canonical key/digests, enforce one exact-scope issuer and prohibit key reuse across deployment/scope histories. It must lock the canonical provider and latest revision, append audited transitions, re-evaluate the actual latest revision without fallback, require proof issuance within the approved issuer window and bind the signed statement to the admitted provider, deployment and issuer revision before any credential-use activation. The provider-qualified proof schema (#5216) and read-only candidate resolver (#5217) are merged; they must be bound to independently qualified authority before operational use. No trust writer, operational verifier, signed material access or runtime authorization is enabled. PostgreSQL concurrency, real provider evidence and independent review remain mandatory.

### Issuer lifecycle shape and custody boundary (#5222)

The provider-qualified registry (#5199), signed evidence (#5216), independent
candidate reader (#5217), and disposable PostgreSQL model-table qualification
(#5219) are merged. They are not operational trust. The new internal pure
transition-shape helper qualifies only an intended append against a latest
exact-scope revision and the complete history for the candidate key digest.
The conservative initial sequence is absent → draft → independently checked
active → revoked; a draft may also be revoked. Re-enrollment after revocation
requires a fresh key and a new draft. No in-place edit, revision reuse, direct
active-to-active replacement, or fallback to older active history is allowed.
This initial revoke-then-enroll rotation is deliberately fail-closed and is
not a zero-downtime rotation contract.

Activation preserves the draft's provider, deployment, scope, key, requester
and validity window, requires a distinct recording checker and approval after
the draft was recorded, and requires the current ready integration. Same-binding
revocation may proceed in the shape model even after expiry or source disablement;
source/provider/deployment drift must not silently retarget a revision.
A typed proof must be issued after the approved active revision was recorded,
and its expiry must not extend beyond the issuer window. Existing signature,
maximum proof lifetime, canonical selector and provider-schema checks remain
mandatory.

The pure helper is not a writer or authorization result. A future governed
caller must derive authenticated source-owner and checker authority from
canonical Access, independently resolve actual provider deployment identity,
custody of the provider-side signing key and exact credential-schema evidence.
An evidence digest, public key, or supplied history alone cannot establish
any of these facts. The writer must lock current provider and exact-scope
history, serialize cross-scope key-digest uniqueness including absent history,
re-read complete committed key history and expected revision, and atomically
append the new revision with sanitized mandatory Activity Audit. Fail closed
on missing evidence, stale state, lock conflicts or audit failure. Real
PostgreSQL concurrent transaction tests and independent custody/Access review
are mandatory before enabling a writer. No new permission, route, migration,
provider request, active issuer, or runtime verification wiring is introduced
by this increment.


### Independent issuer custody evidence qualification (#5224)

The admitted shared KV v2 HTTPS transport in `providers/kv2_http.py` enforces
provider-specific origin/CA settings, rejects redirects and environment
proxy/netrc credentials, and observes health and bounded AppRole metadata.
The OpenBao client additionally checks strict internal active health and
operator audit configuration/mount counts. The Vault client retains its own
transport policy. None of these mechanisms establishes independently pinned
deployment identity, issuer custody, actual credential schema or an Access
decision. A compatible response, TLS peer, endpoint, local instance ID,
configured audit device or successful AppRole login is not a trust anchor.
Bundled deployment ownership must come from the reviewed target bootstrap and
independent recovery authority (#5200/#5202); external ownership requires a
separately reviewed source-owner authority. No admitted resolver for either
custody authority is identified in these mechanisms.

The offline `IssuerCustodyEvidenceShape` contract binds the exact provider,
instance, namespace, mount, deployment and prospective revision, public-key
digest, independently expected challenge digest, and distinct evidence
references for deployment identity, proof of possession, independent custody
and canonical Access decision. It requires distinct source-owner/checker
identifiers and timezone-aware challenge/receipt/approval chronology. The
initial proposed upper bound is 24 hours from challenge issuance, with
exclusive expiry. This is a conservative shape bound, not an operational
challenge lifetime approval. A repeated or wrong challenge is not admissible:
the future locked caller must independently issue, resolve and atomically
consume each challenge exactly once; a pure matcher cannot detect replay of
the same valid inputs, verify signatures, authenticate actors, or detect
revoked or unavailable evidence. Each reference must be independently
resolved and verified against its own authority and the exact binding; four
distinct digests do not prove four independent facts. The current code has
no operational evidence resolver or acceptance path. Missing authority
therefore remains a release blocker, even when synthetic shape tests pass.

Provider-side credential schema validation remains an independent
per-credential/version obligation, not a generic issuer receipt. Canonical
Access and Activity Audit remain mandatory for a future governed writer;
do not create a new permission system or accept caller-supplied approval
flags. Require independent, current deployment/owner/checker/custody evidence,
revocation and replay checks, and atomic audit before admitting a writer.
A real ceremony and disposable provider evidence require separate reviewed
implementation and operator authorization; no signer, key generation, live
provider access, secret retrieval, mutation, migration or worker wiring is
introduced here.


### Issuer proof of possession (#5231)

The offline Ed25519 challenge statement uses the existing compact sorted
ASCII JSON and UTC timestamp conventions. The distinct schema
`kaori.secrets.issuer_possession.v1` binds the complete issuer target,
algorithm, candidate public-key digest, challenge digest, source-owner
identifier, issue time and exclusive expiry. The verifier reconstructs
bytes from independently expected context, checks the raw public-key
SHA-256 digest and verifies the signature using existing offline primitives.
Credential version statement bytes and legacy Vault behavior are unchanged.
The existing proposed 24-hour shape ceiling is reused; it is not approval
of an operational challenge lifetime.

A matching signature proves possession of the corresponding signing key
for that message only. Neither a supplied expected challenge nor a valid
signature proves deployment identity, exclusive custody, authenticated
ownership, checker authorization or actual provider credential schema.
There is deliberately no signer, nonce generator, issuance endpoint,
persistence or acceptance path in this increment. Repeated successful
offline verification is possible and does not authorize anything.

A separate governed implementation must issue unpredictable single-use
challenges, persist only bounded metadata, bind current exact target and
key to authenticated source-owner intent, resolve current challenge state
independently of any response, and atomically consume it with the verified
evidence and sanitized Activity Audit. Deny already consumed, revoked,
expired, missing, substituted or unavailable records without fallback.
The actual deployment identity and independent custody ceremony require
reviewed authority and disposable environment evidence before any active
issuer writer or worker use.


### Inactive single-use issuer challenge persistence (#5235)

The provider-neutral `SecretCredentialIssuerChallenge` model and additive
empty migration store only bounded challenge metadata: exact integration
instance/provider/namespace/mount, prospective revision, deployment reference,
public-key digest, globally unique challenge digest, source-owner foreign key,
issuance and exclusive expiry. No raw nonce, private key, signature, bearer
credential, or provider response is retained. The prospective revision is
intentionally not a foreign key to an active issuer: enrollment precedes
activation. The existing source and user foreign keys are restrictive.

The initial storage states are pending, consumed and revoked. Expiry is
derived from the time window rather than persisted as a mutable status.
Pending has no resolution metadata; consumed requires an independent
recording actor, a possession-evidence digest and resolution within the
issuance window. Revocation can retain expired records, requires a recording
actor and time, and cannot claim possession evidence. Database checks
enforce basic shape and digest lengths, not canonical digest syntax,
actor authorization, verified evidence, clock freshness or state transitions.
The migration refuses to discard nonempty challenge history on downgrade.

This increment has no issuance, consumption, revocation service or runtime
reader. Storage uniqueness prevents duplicate digest insertion, not a
second update to an existing record. A later governed writer must generate
unpredictable challenges, derive canonical inputs from authenticated
source-owner intent, independently resolve current binding and authority,
lock the pending record, verify possession, and atomically transition once
with sanitized Activity Audit. Never reset a terminal row, accept a
caller-provided verified flag, or delete history to allow replay. Use actual
PostgreSQL concurrency/rollback qualification before enabling the service.
The previous proposed 24-hour offline shape ceiling remains non-operational;
the issuance service must enforce a separately reviewed lifetime. Actual
custody and deployment evidence, Access, issuer writer and worker admission
remain mandatory. No seed, backfill, live migration or operational trust
is introduced.


### PostgreSQL challenge storage qualification (#5237)

The disposable CI-only qualification uses the exact #5218 database target
guard and a unique test-owned schema. It invokes the actual #5235 Alembic
upgrade/downgrade functions, checks reflected schema parity and restrictive
foreign keys, verifies global digest uniqueness and committed timestamp
visibility, and exercises actual competing READ COMMITTED transactions.
The test observes PostgreSQL blocking PIDs before releasing the first
transaction, with bounded lock/statement timeouts. A pending-only update
includes the exact stored binding and resolution window; commit/rollback
and competing consume/revoke cases qualify the storage primitive only.

No application writer, operational nonce issuance, Access decision,
cryptographic verification, Activity Audit or custody authority is
introduced by these tests. The later governed service must repeat
transaction qualification against its actual independently resolved
inputs, canonical authorization and atomic audit behavior; the test-only
update is not a production acceptance path. No live database is migrated.


### Governed credential issuer authority (#5245)

Maintainer architecture acceptance is recorded in #5245 comment 7205030372.
Issuer administration uses three distinct explicit permissions
(`secrets_pki.request_credential_issuer`, `secrets_pki.approve_credential_issuer`,
`secrets_pki.revoke_credential_issuer`) with `secrets_pki.view` dependency
and no default role grants. The canonical ScopeAccessPolicy owns the exact
`credential_issuer` scope: instance, provider derived from IntegrationInstance,
namespace, mount and immutable deployment digest. The additive nullable
`issuer_deployment_ref` is restricted to that scope; legacy policies retain
null. Downgrade refuses to discard issuer grant history. No grant backfill.
The locked Access precondition reads the authenticated actor's active role
and actual permission memberships, source, exact scope policy and latest
revision, denies ambiguity and stale pointers, and permits only explicitly
scoped revocation of a disabled same-provider source. It does not establish
provider deployment identity, custody or an authenticated HTTP caller.
No existing metadata grant or worker-use permission can substitute for it.

Use provider-native non-exportable Ed25519 Transit keys with explicitly
qualified key version; never copy signing private keys into KAORI. Independent
deployment/custody attestation must come from an operator-held recovery
authority pinned outside provider-controlled or web-writable state. The
receipt must bind verified native deployment identity, provider, exact target,
Transit key/version and public-key digest, with independent owner/checker,
validity and revocation evidence. Neither Transit signature nor a local
policy proves custody or typed SSH credential schema. Challenge issuance
uses a 256-bit random value digest and a 10-minute exclusive lifetime.
The transaction service must derive and verify these authorities, acquire
current policy/source/challenge/history locks, serialize key digest
uniqueness, and commit lifecycle, one-time challenge and mandatory audit
atomically. The permission/scope increment alone does not expose a grant
writer, operational challenge acceptance or issuer activation. Complete the
service, provider evidence integration and PostgreSQL qualification within
the same draft candidate before admission; actual custody ceremony and UAT
remain separate operator-approved execution.


#### Native provider key and independent receipt resolution

The shared `providers/issuer_transit.py` adapter performs only exact native
key metadata inspection. It requires provider-specific HTTPS egress and
explicit CA, strict active/unsealed cluster identity before and after the
read, bounded non-root expiring inspection token, safe single-segment
Transit mount/key, explicitly pinned current version and Ed25519 public-key
digest. Missing or unsafe key-policy fields, native key rotation, wrong
cluster, malformed public key, derived/exportable/deletable key or plaintext
backup permission deny. The native `vault:vN:<base64>` signature envelope
must match the enrolled version before offline verification. No generic
signing, key export, key management, KV material read or provider fallback
is exposed. Native response semantics and token ACLs require actual
disposable provider qualification; synthetic fixtures do not prove those.

The deployment-owned authority directory is fixed at
`/run/kaori/issuer-authority`. It must be root-owned, non-writable to app
identity, mounted read-only, with a separately pinned Ed25519 `root.pub`
(raw lowercase hex). The resolver reads canonical JSON envelopes with
exact `payload` and hex `signature` fields. Active deployment receipts are
named `deployment-<deployment_ref>.json`; challenge-specific custody
receipts are `custody-<challenge_sha256>.json`. The domain-separated
schemas bind exact scope, native cluster identity and Transit key version,
public-key digest, distinct owner/checker, UTC issue and expiry and
challenge/revision context. The recovery pin must differ from the issuer
key. The deployment digest binds provider/instance/namespace/KV mount,
canonical endpoint and native cluster ID, independent of key rotation.
Current signed receipts are read afresh for each decision; absent/revoked,
expired, malformed, substituted or noncanonical evidence denies. Revocation
requires operator replacement/removal of the current authoritative file;
application users cannot write this directory. Protect the directory and
operator publication channel against rollback, prove trusted mount identity
and test atomic publication/revocation before actual activation. Receipts
are limited to 24 hours and a custody receipt cannot outlive the challenge
or deployment receipt. Native observation must be no more than 60 seconds
old when custody is qualified. The service must acquire observation itself
outside SQL locks and re-resolve trusted evidence and Access inside its
transaction. The read-only resolver is not an issuer writer, independently
authenticated operator or proof of exclusive private-key custody.


#### Internal governed grant and enrollment transactions

`issuer_grants.py` uses the canonical Access administrator guard, existing
policy/revision storage and commit-with-Activity-Audit primitive. Request
creates only a draft, approval needs a distinct administrator other than
the subject, and revocation appends history without requiring provider
availability. The signed enrollment receipt restricts the requester and
checker subjects. No public administrative route or automatic role grant.

`issuer_lifecycle.py` requires PostgreSQL READ COMMITTED, rejects dirty
session state, and uses a bounded domain-wide transaction advisory lock
before current issuer policy/source/history/challenge locks. The conservative
domain lock serializes even absent histories and cross-scope key reuse; it
trades issuer enrollment throughput for simpler correctness. The service
qualifies Access before native read, releases that transaction before network
IO, then rechecks locked Access and independently rereads current receipts.
For Vault it also checks the canonical connection endpoint/namespace/KV
mount/TLS without loading the AppRole secret. OpenBao uses the signed
operator enrollment mapping pending provider registration qualification.
Draft and its one-time prospective activation challenge are committed
together; the random 256-bit challenge digest, 10-minute maximum expiry and
exact expected revision are generated by the service. The checker must
present a versioned native signature of the returned canonical statement
and current independently signed challenge custody receipt; the owner's
request permission is also re-evaluated. Consumption, active append and
sanitized mandatory audit share one transaction. Revocation appends an
exact same-binding terminal revision and revokes any matching pending
challenge, even when the provider is unavailable. No reset, retry with
old challenge, older active fallback or raw signature persistence.

This internal source candidate is not operationally enabled. Actual
authority directory publication/revocation anti-rollback, provider
registration/TLS/ACL/native metadata, authenticated caller and currentness
of external evidence must be independently qualified. The database lock
cannot serialize an external filesystem publication or provider state
change; provider observation is bounded but not a distributed transaction.
Transaction-bound credential-use verification remains a separate worker
workstream. No live provider request, key operation or migration is
authorized by this implementation.


The issuer grant and enrollment services share the same bounded PostgreSQL
transaction serialization and explicit role-membership locking. The
disposable service suite uses canonical tables, actual Access grant
transitions, actual Ed25519 receipt/signature verification, real committed
issuer/challenge/audit writes, stale/withdrawn authority negatives, audit
flush rollback and competing independent application contexts. Only the
operator filesystem and provider network observation are substituted with
synthetic fixtures. Source tests do not substitute for successful CI or
actual provider/ceremony UAT.


#### Consolidated source audit

All issuer lifecycle and issuer-specific grant mutations require a clean
service-owned PostgreSQL transaction; an existing caller transaction cannot
be committed by an issuer operation. The generic Access revoke path rejects
issuer scopes, so the issuer-specific grant writer owns the shared lock.
Recheck evidence, observation age and grant/issuer validity after row locks;
for activation re-read the exact custody receipt before staging audit.
Signed scope comparisons use canonical encoding (boolean IDs cannot equal
integer IDs). Test the actual scope migration downgrade/upgrade against
legacy policy rows, retained-history downgrade refusal, generic grant revoke
denial, and service approval/revocation contention. External authority
publication and native observation remain outside PostgreSQL's transaction;
actual monotonic publication, revocation and deployment UAT are still
mandatory and cannot be inferred from a successful database transaction.
