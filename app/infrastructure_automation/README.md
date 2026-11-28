# Infrastructure Automation — guarded localhost worker pilot

Authority: #556, #4796, #4799, and OXY7O/kaori-operations#1. **Non-production read-only smoke only**. The operator-facing Ansible provider, remote SSH credentials, cluster create/upgrade/patch and production execution image are NOT implemented here.

## Review/UAT contract

- The immutable source revision is `OXY7O/kaori-operations@aa5ae076e0cd5e6a2cc4d236608cb470012a7ab2`. Its source manifest, playbook and localhost inventory are restricted to one allowlisted operation: `linux.host_facts.v1`.
- The pilot source is the accepted `kaori-operations#8` merge into the parent issue branch, with identical tree to reviewed `b47ee61042e161bf2f6ea22de0d57a6873459393`. Pin Ansible Core 2.19.15 and Runner 2.4.3; the former vulnerable source SHA is rejected. Parent upstream #2 remains subject to independent review. This exact source is restricted to localhost and is not the separate Kubespray source profile. No real-host SSH or cluster mutation is authorized.
- KAORI's existing `enqueue_canonical_job` dispatches a `JobExecution` through a **dedicated `automation` Celery queue**; worker concurrency 1. The task is in `app.infrastructure_automation.tasks`, not a synchronous Flask route.
- Both dispatch and execution **fail closed** unless `APP_ENV` is `development`/`testing` and `KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true`.
- Runner output is reduced to bounded Linux OS/kernel facts and a source SHA in committed JobExecution. Temporary Runner artifacts are deleted; **environment image attestation remains NOT VERIFIED**.
- There is no arbitrary host selector, SSH key, become, extra variables, Kubernetes mutation, schedule, or user-visible provisioning action.

## Guided Dev Container UAT (local host only)

1. On the approved Dev Container, clone `OXY7O/kaori-operations` into `/workspace/kaori-operations`, checkout exact SHA `aa5ae076e0cd5e6a2cc4d236608cb470012a7ab2`, and require `git status --porcelain` to be empty.
2. Install dependencies into the Dev Container test Python environment from `/workspace/kaori-operations/execution-environments/requirements.txt`. Never modify the production image during UAT.
3. Run normal KAORI PostgreSQL/Redis/app prerequisites. In its own terminal start the isolated automation worker with: `APP_ENV=development KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true celery --app celery_worker:celery_app worker --queues=automation --concurrency=1 --prefetch-multiplier=1 --loglevel=INFO --hostname=automation@%h`.
4. In a second terminal, invoke: `APP_ENV=development KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true flask --app run:app automation-localhost-probe --source-path /workspace/kaori-operations --source-sha aa5ae076e0cd5e6a2cc4d236608cb470012a7ab2`.
5. Review **Platform Operations → Jobs & Executions → Executions**. The new JobExecution must include the approved operation, immutable SHA, bounded OS/kernel facts, `changed=false`, and `environment_attestation=NOT VERIFIED`. Check worker log for no secret or raw event output.
6. Negative: disable the flag, provide an invalid SHA, dirty the Git checkout, or stop the automation worker; operation must be blocked and no false successful JobExecution created.
7. Record actual case IDs/commands/SHA, sanitized results and explicit Human Acceptance on issue #4799; stop the worker and disable the pilot flag afterward.

**Not a production-ready feature:** no remote provider identity, credential authority, image digest, trusted SSH inventory, managed Kubernetes capability or real infrastructure mutation. Do not treat localhost UAT as cluster provisioning evidence. See #4800–#4802 for subsequent gated workstreams.

## Focused pre-UAT quality checks (in existing Dev Container)

Run against this exact work-branch source before asking for Human UAT:

```bash
python -m ruff check app/infrastructure_automation app/commands/__init__.py app/config/default.py tests/contracts/platform_operations/test_ansible_localhost_worker_contract.py
python -m ruff format --check app/infrastructure_automation/*.py app/commands/__init__.py app/config/default.py tests/contracts/platform_operations/test_ansible_localhost_worker_contract.py
python -m pytest -q -p no:cacheprovider tests/contracts/platform_operations/test_ansible_localhost_worker_contract.py
```

Optional **image build-only** smoke (no deployment/runner execution) for the isolated pinned worker target:
`docker build --target automation-worker --tag kaori-automation-worker:uat .`

The default Dockerfile final target remains `production`; this opt-in `automation-worker` target is not part of either default Compose worker fleet. Both localhost facts and review-only Kubespray Plan tasks have explicit canonical routes to the existing dedicated `automation` queue (#4980). The Celery topology verifier validates this concrete isolated target, non-root command, exact two-task ownership and absence of default/Beat activation separately from the ten default worker queues. The ordinary fleet must never consume `automation`; a live, separately admitted worker advertising the task is still required by the canonical dispatcher. The manual Dev Container worker remains opt-in; do not enable it or the localhost pilot flag on hosted staging/production. A successful build is not equivalent to runtime/Dev Container/real-provider UAT. Record all command results, SHA, environment and any blocker; do not mark NOT RUN as PASS.

## Scoped host access reference qualification (#5162)

The existing reference review now has a stricter internal `assess_scoped_host_access_references` boundary for future authorized callers. It requires an active exact host membership, a matching active ready same-environment Vault source, matching ready collection generation within the existing 24-hour metadata freshness bound, and the exact current observed available KV v2 version. The guard requires undestroyed current version metadata with no deletion timestamp (including future deletion intent). It does not import the Secrets & PKI application domain or duplicate its lifecycle classifier; deleted, destroyed, scheduled-deletion, wrong-source, stale and mismatched records fail closed. The underlying reference-shape helper alone is not sufficient for operational selection.

Inputs must be resolved from authorized committed records under canonical #724 scope policy and audited access. This pure comparison does not execute that policy, establish complete collection coverage, qualify SSH key type or authorize material use. It does not persist a binding or expose a selector. The actual governed selector, credential-use policy, trusted host-key evidence producer and worker attestation remain gated under #5162/#4799/#5066. No raw material, SSH probe, queue dispatch or Run authorization is introduced.


### Persisted candidate identity (#5162)

`AutomationHostAccessBinding` owns one reference-only candidate per existing
inventory assignment. It stores the canonical Secret representation foreign
key, pinned version number, host revision, reference fingerprint, public-key
digest candidate and actor/time provenance. The version is a pin, not a
foreign key to transient version-observation rows: provider metadata refresh
or retention must not be prevented by a reference. Readback must requalify
the exact currently observed version and source using the existing guard.
An absent row, changed host revision, credential version, source/EE or
fingerprint cannot yield a current reference. A candidate key digest is not
a verified key or a known_hosts artifact.

The migration adds storage only; there is no backfill, automatic selection,
public writer or selector. A subsequent governed transaction must enforce
canonical Access policy, exact mount/host scope, independent credential-use
authority and mandatory audit before recording a reference. The internal
readback contract cannot authorize material retrieval, SSH or a Run.

## Independent SSH host-key trust — qualification proposal (#5183/#5185)

The accepted security direction in #5183 separates a recorded key digest from
independent trust. The initial proposed out-of-band source is the authorized
VM/hypervisor or physical console of the exact enrolled disposable Linux host,
with verification by a distinct authorized human. The console provenance must
be independently reviewable; a key first observed over the network, a
successful SSH session, or an operator-entered digest alone is not evidence.
This source and reviewer scope require explicit qualification before a writer
is introduced.

The future trust record must correlate the canonical assignment and host
revision (including exact IP address and SSH port), reference fingerprint,
key algorithm and canonical public-key digest, source provenance reference,
requester/verifier, verification time, expiry and revision/revocation state.
A first pilot should qualify a single supported host-key algorithm and exact
public-key encoding before accepting evidence; no generic arbitrary algorithm
or opaque digest substitution. Do not store private material or raw console
output in KAORI audit or JobExecution. A digest alone cannot construct a
known_hosts entry; the independently verified public key must be available
through the qualified trust source at the later worker boundary. Never disable
strict host-key checking, trust on first use or fall back to another key.

The existing metadata-only candidate remains non-authorizing even with a
current grant. Port, role and key-digest drift now have explicit persisted
reference/Plan correlation regression coverage. Independent trust must remain
separate from candidate evidence and must be requalified after endpoint,
assignment, key, credential version, source or policy changes. Revocation and
expiry must invalidate affected preflight/Plan evidence. No trust record
writer, live SSH, key acquisition, worker authorization or credential use is
enabled by this increment. The next storage and lifecycle implementation
requires independent review of the concrete source, verification and expiry
contract.

### Canonical public host-key encoding (#5185)

The first supported algorithm is OpenSSH `ssh-ed25519`. The canonical value is exactly the two ASCII fields `ssh-ed25519 BASE64` (no comment, newline, certificate, options or other algorithm). The encoded public key must parse and round-trip through the existing cryptography library; the stored candidate digest must match SHA-256 of the decoded SSH wire blob, encoded as `sha256:` plus 64 lowercase hexadecimal characters. This is not a digest of the text file, a private key, or a verified console attestation. No conversion from an unqualified opaque candidate is automatic: obtain the independently reviewed console public key and compare the exact digest.

The offline helper `qualify_ed25519_host_key` returns a canonical public key or denies. A match does not prove who collected it, host identity, expiry, authorization or reachability. The later governed trust lifecycle must bind this public key to the current committed host/endpoint and candidate, independent verifier and provenance; only the qualified worker may generate its ephemeral strict known_hosts file. No network acquisition, SSH, credential retrieval or execution is introduced by this increment.

### Independent SSH trust revision persistence (#5185)

`AutomationHostTrustRevision` preserves intended append-only evidence per canonical inventory assignment, with a unique monotonic revision number. Each revision pins the host revision, binding fingerprint, exact address/port, canonical Ed25519 public key and wire digest, independent console source and opaque evidence reference, requester, verifier, recording actor and validity timestamps. Draft, active and revoked are distinct; an active row requires an independent verifier and a valid verification timestamp. Revocation evidence may be retained even after expiration. No backfill or active trust is created by the migration; downgrade refuses to erase recorded evidence.

Storage shape alone is not trust. The subsequent governed writer must lock the assignment and latest revision, verify current candidate/source/endpoint and the exact public key, independently establish the console evidence and verifier authority, append the next revision with mandatory Activity Audit, and deny stale or ambiguous evidence. The runtime reader must requalify the latest active unexpired revision and never fall back to a superseded active row. No private material, network acquisition, known_hosts generation or SSH execution is enabled by this storage increment. PostgreSQL migration/concurrency and real independent console evidence remain separate admission requirements.

### Proposed independent console evidence protocol — review required (#5185)

The initial non-production pilot uses an independently authenticated existing VM/hypervisor or physical console, not a network SSH key scan. The verifier is a distinct authorized human, neither the trust requester nor the candidate binding recorder. The verifier independently confirms the console asset's canonical enrolled host identity, IP/port and actual configured Ed25519 server public key; the source host owner must resolve any ambiguity before verification. Only the canonical public key and SHA-256 wire digest are eligible; no private key, login token, raw console transcript or screenshots containing secrets belong in KAORI.

Proposed evidence reference: `sha256:<64 lowercase hex>` of a restricted, immutable, sanitized console verification artifact retained under operator evidence custody. That artifact must identify the canonical assignment/host revision, endpoint/port, binding fingerprint, public key/digest, console asset identity, authorized verifier and verification UTC instant/expiry. The independently authenticated reviewer must inspect and match the artifact and source; a hash or free-form operator assertion alone is not provenance. Artifact custody and concrete verifier authorization must be reviewed under #5185 before a writer is enabled. The recording actor for an active verification revision is the verifier. These are proposed additional constraints, not an already established provider integration.

The offline `trust_revision_candidate_matches` helper checks only the structure of the supplied latest revision against the current assignment and candidate binding, strict key encoding, proposed digest-shaped evidence reference, independence fields and unexpired UTC window. It does not query the latest row, prove audit or artifact custody, authenticate the verifier, qualify current provider/source metadata, or establish SSH trust. Future governed callers must lock the canonical assignment, resolve the actual latest revision without filtering to active rows, requalify full current reference and source metadata, verify the external evidence/actor authority, and append an audited revision. No writer, known_hosts generation, worker connection, credential access or trust activation is introduced here.

### Latest trust revision and audited revocation (#5185)

The internal `latest_host_trust_revision` reads the highest revision for the exact assignment without filtering by lifecycle state. Its caller owns access scope; writers must lock the assignment before reading the latest row, even when no history exists. A revoked latest revision may not be bypassed by an older active row. This read is not a trust or execution decision.

`revoke_host_trust` appends a revoked revision to the current active row using the authenticated actor, exact Ansible connection and assignment and expected revision. The proposed revocation authority reuses canonical Access grant-administrator eligibility (explicit roles.manage and users.manage), plus integrations.manage and inventory.view. This narrow internal administrative boundary requires independent review; no new permission or route is registered. Revocation intentionally remains possible for expired proof or disabled/retired inventory; it must not depend on an otherwise qualified current credential or live provider. The transition preserves prior evidence and stages sanitized Activity Audit in the same transaction, rolling back on failure. Audit excludes endpoint, key, digest and console evidence reference. No active trust writer, independent console verification, replacement, known_hosts generation, Plan authorization or SSH is enabled. PostgreSQL concurrency and real operational UAT remain mandatory.


### Local Kubespray provider KV v2 readback currentness (#5257)

The approved disposable `flask automation-inventory-store` CLI remains the only entrypoint for a provider KV v2 inventory/config readback. The existing `--publish` operation uses CAS-zero immutable creation, while default compare and `--check-ansible` are read-only and independently recheck source, host assignments, provider cluster, token authority and exact KV v2 version-one readback. Ansible parses the fixed compiled inventory offline; no arbitrary playbooks, SSH or inventory plugins run.

A successful new readback records a schema-versioned **historical receipt** on the canonical Ansible IntegrationInstance, including exact provider/cluster/mount correlation, SHA-256 of the registered provider origin (not an endpoint credential), immutable document fingerprint, reviewed Git source SHA/repository, committed host fingerprint, non-secret pod/service network intent, parser check result and observation UTC instant. It contains no KV value or token, secret path, private key, login material, executable inventory, or approval. Previous receipts lacking this schema remain `unqualified`; run the approved compare and native parser step again rather than interpreting them as current.

The permission-scoped Infrastructure Automation → Kubernetes Lifecycle detail now projects this receipt against **current KAORI committed intent** and the exact registered OpenBao or Vault provider record. Normal GET uses bounded database queries only; it never reaches OpenBao, Vault, GitHub, Ansible, SSH or the Kubernetes API and never hydrates provider SecretID. It renders `Historical Source Aligned` only if the source/host/network immutable document and provider origin still match the receipt, and shows `Review Required` for missing, changed, parser-unchecked or unqualified evidence. Credential-free UI never displays provider KV paths. The status is not an assertion that the provider entry currently exists, is fresh, or grants operational access.

**Dev Container verification sequence:** use an independently authorized disposable non-production Ansible connection and three registered lab hosts; keep the exact approved Vault/OpenBao KV v2 mount and provider-specific TLS/cluster constraints; run an explicit `--publish` once, then a separate `--check-ansible` readback using a bounded transient non-root token, and refresh the Infrastructure Automation page with `inventory.view`. Confirm historical-aligned evidence, then change one source/host/network/provider origin in a disposable fixture and confirm denial. Revalidate the actual external provider, authorization, audit delivery and independent human acceptance before treating any evidence as admissible. Source-only, no-provider, sealed, wrong-cluster or expired-token scenarios must report blocked/pending, not PASS.

This is independent review evidence only. It does **not** feed an executable Plan approval or grant worker access; #5162/#4799/#5066, maker/checker, approved change window, #4801 genuine non-production provisioning, Kubernetes API verification and final #5172 Human Acceptance remain mandatory. The review branch is a temporary UAT holding lane under #2227, not official staging, main, RC or release authority.


### Local OpenBao metadata-bound host access (#5204)

The canonical Access grant lifecycle accepts an isolated `openbao_mount` metadata-read
scope for the independently selected local development provider and exact KV v2 mount.
It does not inherit or reinterpret `vault_mount` policies. Request and independent
approval remain required; no defaults or credential-use grant activation are added.
Set `KAORI_LOCAL_OPENBAO_INVENTORY_PROVIDER_ID`, `KAORI_LOCAL_OPENBAO_INVENTORY_MOUNT`
and `KAORI_LOCAL_OPENBAO_AUTOMATION_ENVIRONMENT` to the independently approved local
provider, mount and exact non-production Ansible environment before recording a
candidate. A successful OpenBao validation stays degraded pending independent
credential authority; only its connected metadata reference is eligible, with
fresh complete inventory and exact version checks. OpenBao reference fingerprints
include the deployment identity, ownership, endpoint, cluster, mount and environment;
legacy Vault fingerprints retain schema v1. Changes to the selected source or
environment invalidate currentness. No key retrieval, issuer proof, SSH admission,
credential activation, execution or new HTTP action is enabled by this slice.
Migration and independent review are required before broader admission.


### Exact typed credential evidence and approval precondition (#5184/#5204)

The internal `resolve_current_credential_evidence` requalifies the canonical
automation credential target under the caller's policy/target transaction.
It resolves the latest issuer revision without filtering to active rows,
requires the current independently signed deployment receipt and matching
canonical source, and reconstructs the existing provider-qualified statement
from the exact committed representation/version/creation timestamp. No caller
can choose a verification key, provider path, proof, issuer revision or type.

Proposed independent evidence format for review: on the existing operator-owned
read-only `/run/kaori/issuer-authority` mount, `credential-<sha256>.json` is
named by SHA-256 of canonical JSON `{"selector": asdict(selector)}`. The
canonical signed envelope uses schema `kaori.secrets.typed_credential_evidence.v1`
and binds current deployment evidence digest, committed issuer evidence digest,
issuer public-key digest, exact statement SHA-256, 64-byte issuer signature
encoded as lowercase hex, independent source owner/checker IDs and UTC
issuance/expiry. The independent root signature attests that the provider owner
actually inspected the exact credential schema and that custody remains current;
the provider issuer signs the existing exact-version statement. Both signatures
and the independent deployment receipt must be current. This is a candidate
evidence contract, not a new general signing or secret-inspection API; the
provider-owned producer and actual native schema inspection require review/UAT.
Removal, expiry, identity/version/issuer drift deny. No raw secret is read.

`review_credential_grant_approval` additionally locks the current policy,
latest draft revision, maker/checker/principal explicit permissions and target.
The approver is distinct from both maker and principal; proof must cover the
proposed grant window. The return is redacted evidence only. No active grant,
new route, credential material, provider call, SSH, worker dispatch or runtime
authorization is created by this review-only slice. PostgreSQL locking and
independent Access review remain required before adding an approval writer.


### Independent signed console evidence review (#5185)

The proposed console authority uses a distinct, operator-owned read-only
`/run/kaori/ssh-trust-authority` mount and independently pinned Ed25519
`root.pub` (lowercase raw public-key hex). The shared hardened authority file
reader rejects writable mounts, symlinks, non-root ownership and oversized
artifacts. The console authority must be independent of the managed host and
Secrets issuer. No private key is provisioned into KAORI.

The fixed artifact name `console-<sha256>.json` derives from canonical JSON
`{"target": asdict(target)}`. Schema
`kaori.automation.ssh_console_evidence.v1` is a signed canonical envelope
binding exact Ansible connection, assignment, canonical host and revision,
reference fingerprint, address/port, host-key digest, intended trust revision,
requester and distinct verifier. It carries the canonical public key,
independent console asset evidence digest, verification UTC and expiry
(maximum 24 hours), not a raw console transcript. The signature attests
independent console inspection, not mere possession of an opaque digest.
The native host key itself cannot act as the signing root.

`review_console_trust_activation` requalifies the locked exact committed
credential target, including provider/source/current version metadata, then
checks explicit requester/verifier permissions and the proposed next trust
revision. Initial or explicitly revoked prior state only; no active-row
overwrite. `review_current_console_trust` also re-resolves the latest active
revision and matches its public key, verification/expiry and evidence digest
against the current signed artifact; removed/revoked/changed evidence fails
closed. Neither service writes a trust revision or grants credential use,
creates known_hosts, probes SSH, dispatches a worker or authorizes a Plan.
The proposed console authority, artifact custody, verifier permission
combination and actual independent operator inspection require review and
real UAT before the activation writer is enabled.


### Local candidate activation and combined evidence (#5184/#5185)

The review-lane candidate implements internal `approve_automation_credential_grant`
and `activate_host_console_trust` writers. They are disabled by default.
The local deployment must explicitly opt in with
`KAORI_LOCAL_AUTOMATION_SECURITY_REVIEW=1` and both environment and Flask
`APP_ENV=development`. Do not enable the flag until independent Access/security
review of the preceding typed proof and console custody contracts. PostgreSQL
READ COMMITTED and a clean transaction are required; the local writer lock
serializes activation, and canonical policy/assignment locks coordinate
revocation. No HTTP route, CLI command, role grant, fixture authority or
production enablement is added. The flag must never be interpreted as worker,
provider material or infrastructure-mutation authority.

Credential approval requires an independent checker distinct from requester
and principal, current exact target and typed provider proof covering the
grant window, and no overlapping active grant for the same principal/assignment.
The canonical active policy revision stores the exact proof digest, not secret
material. The nullable migration preserves legacy history and refuses downgrade
if approved evidence would be lost. The independent trust writer appends the
next revision only after initial or explicitly revoked state, verifies the
exact signed console evidence and rechecks the latest committed-shape record.
Both writers stage Activity Audit and requalify evidence before commit;
denial or audit failure rolls back the entire transition. Existing canonical
revocation remains available independently of evidence availability or opt-in.

`review_current_credential_grant` resolves a unique latest active exact policy
and rechecks actor, maker/checker, binding, issuer and pinned proof digest.
`review_remote_access_evidence` requires both this grant and current independent
SSH console trust, and returns only a bounded correlation digest and expiry
with execution_authorized=false. It cannot be used as a transferable permit.
The future remote worker must independently qualify signed EE/source,
actual operation/target approval, native credential material delivery,
strict host-key validation, and job/audit admission immediately before use.
The frozen source profile is still non-executable; no worker or provisioning
has been enabled by this slice.

Tests include isolated CI PostgreSQL candidate lifecycle cases with synthetic
provider proof, signed synthetic console artifacts, revocation, rollback and
combined readback. Native provider schema inspection, real independent console
custody, migration execution, quality gates and operator acceptance remain
pending on the exact review head.


### Remote preflight source, target and worker evidence candidate (#5186)

The accepted Kubernetes lifecycle profile remains pinned to its existing
review-only source. The upstream remote facts candidate in
OXY7O/kaori-operations#10 is still disabled and unaccepted. The new
`review_remote_source_candidate` checks the exact candidate Git SHA,
origin, clean checkout, fixed playbook/manifest/config/requirements blob
hashes and disabled manifest shape. It does not repin the accepted profile
or run Ansible.

`review_remote_preflight_target` reads the exact current canonical connection,
bounded 1-control-plane/2-worker inventory, historical provider KV v2
readback and parser evidence, and combined current grant/console evidence
for the same initiating actor on every member. It returns only correlation
and internal fact-target aliases, capped by the shortest evidence window and
15 minutes. Historical inventory readback is not live provider currentness;
the future admitted worker must check the native exact document again.
No material retrieval or dispatch occurs.

Proposed external worker review artifact: separate root-owned read-only
`/run/kaori/automation-worker-authority`, independent Ed25519 `root.pub`,
and a `worker-<sha256>.json` artifact named by the hash of the canonical
worker selector. Schema `kaori.automation.remote_worker_review.v1` binds
the exact candidate SHA/blob fingerprint, committed profile SHA, EE digest,
pinned Ansible versions, expected worker identity/automation queue, actor,
connection, inventory and target review fingerprints. The signed envelope
also binds independent provenance and target-ownership evidence digests,
reviewer (distinct from initiating actor), UTC issuance and expiry.
The reader verifies signature, exact selector and bounded expiry; the
external authority must actually verify OCI signature/provenance and
runtime identity. This does not measure runtime identity, authorize an
operation, consume a one-time job permit, or replace source acceptance.
No runtime permit is returned, and no task is registered.

`normalize_remote_facts` is a candidate three-host facts adapter. It accepts
only the exact aliases and one successful unchanged setup event per member,
rejects mismatched recap, failed/unreachable/changed/unknown actions and
unbounded events/mounts, and projects bounded OS/kernel/package manager,
CPU/RAM/root disk and effective user ID. Unsupported OS or insufficient
capacity is reported without promotion. It never treats effective UID,
setup network or clock observations as proof of sudo, inter-host reachability,
CIDR completeness, time synchronization or independent host identity.
The separate facts-only result contract is deliberately not the existing
canonical full Kubespray preflight result; no false Ready is introduced.

Independent source acceptance, actual signed EE/native runtime attestation,
separately approved disposable targets, ephemeral worker-only material,
strict host-key transport, canonical JobExecution/audit admission, and
native read-only UAT remain required. Regression cases are synthetic and
do not establish actual provider/host behavior.
