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
