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
