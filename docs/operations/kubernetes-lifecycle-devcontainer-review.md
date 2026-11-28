# Kubernetes Lifecycle — Dev Container exploratory review

Authority: #5186, #4801, #5172 and #2227. This is a non-release review
workbench handover, not native host UAT or mutation admission. The existing
Operations Center workspace reads committed state. #5172 is the single
end-to-end acceptance gate; the individual sections below are qualification
checkpoints, not invitations to accept partial delivery.

## 1. Prepare the existing local worktree

Use the normal KAORI Dev Container and its **local disposable** PostgreSQL
database. Preserve any uncommitted work. If the worktree is clean:

```bash
cd /workspace/kaori
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD
git status --short
flask --app run:app db current
flask --app run:app db heads
```

If migrations are pending, use the existing local migration procedure
only after confirming the database is the intended disposable development
database and taking any required backup. Do not migrate a production or
shared database for this review.

## 2. Qualify the complete review candidate without real hosts

Install the existing development requirements in the disposable Dev Container.
`bcrypt==5.0.0` is development-only and permits creation of the encrypted
OpenSSH negative-test fixture (#5456); do not skip the negative assertion or
add password-authentication support. Do not install into a production worker.

```bash
python -m pip install -r requirements/dev.txt
python -m pip check
python -m pytest -q \
  tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py \
  tests/contracts/integrations/test_ansible_source_posture_contract.py \
  tests/contracts/platform_operations/test_automation_host_enrollment_5168_contract.py \
  tests/integrations/test_ansible_public_git_source.py \
  tests/integrations/test_ansible_kubespray_preflight.py \
  tests/integrations/test_automation_host_identity_5161.py \
  tests/integrations/test_automation_inventory_store_5257.py \
  tests/integrations/test_automation_inventory_receipt_5257.py \
  tests/integrations/test_kubespray_inventory_intent_5155.py \
  tests/integrations/test_ssh_host_key_5185.py \
  tests/integrations/test_ssh_trust_candidate_5185.py \
  tests/integrations/test_kubespray_execution_compatibility_5156.py \
  tests/integrations/test_kubespray_plan_approval_4800.py \
  tests/integrations/test_kubespray_plan_currentness_contract.py \
  tests/integrations/test_kubespray_plan_dispatch_contract.py \
  tests/integrations/test_kubespray_plan_review_contract.py \
  tests/integrations/test_kubespray_plan_worker_contract.py \
  tests/integrations/test_kubespray_run_reservation_4801.py \
  tests/integrations/test_kubespray_run_recovery_4801.py \
  tests/integrations/test_kubespray_independent_verification_4801.py \
  tests/integrations/test_ansible_cluster_binding_read_model.py
```

The existing registration HTTP regression additionally requires a dedicated
**temporary** PostgreSQL `TEST_DATABASE_URL` (its fixture creates/drops schema).
Never set this to the running Dev Container application database or a shared
server database. Record skipped cases separately; a skipped database suite is
not qualification.

```bash
python -m pytest -q tests/integrations/test_ansible_provider_registration_web.py
```

Run the existing security/worker/transaction regression batch as well:

```bash
python -m pytest -q \
  tests/integrations/test_remote_review_diagnostics_5186.py \
  tests/integrations/test_remote_preflight_review_5186.py \
  tests/integrations/test_remote_job_review_5186.py \
  tests/integrations/test_remote_review_posture_5186.py \
  tests/integrations/test_remote_credential_draft_5184.py \
  tests/integrations/test_native_credential_reader_5204.py \
  tests/integrations/test_ephemeral_ssh_material_5204.py \
  tests/integrations/test_kubespray_run_adoption_4801.py \
  tests/platform_operations/jobs/test_job_transactional_persistence.py \
  tests/contracts/platform_operations/test_infrastructure_automation_workspace_5157_contract.py
```

Run the canonical Ruff, Ruff Format, Pyright and DjLint checks as recorded
in #5172. These commands are operator instructions, not claimed results.
Tests use synthetic data/mocked provider and worker boundaries. Never
insert synthetic proofs into the running application database.

## 3. Inspect the real committed setup

Start at Integrations → Orchestration → Ansible. Register or update the
existing eligible source-only connection using Validate Source and Save
Changes. Approved repository and candidate pins are authoritative in
`app/infrastructure_automation/kubernetes/source_policy.py`; do not use
superseded versions or arbitrary source. An existing unused source-only
connection can retain its ID under #5449; dependent configuration revisions
remain blocked under #5453. No new connection is necessary solely to edit an
eligible unused connection.

Then open Operations Center → Infrastructure Automation → Profiles →
Kubernetes Lifecycle and select the connection. Use Hosts & Inventories for
existing-host roles and committed inventory receipt, Plans for readiness and
Plan evidence, and Runs & Evidence for execution records. Remote Preflight
Review under Plans requires jobs.view and shows Not Recorded until a real
canonical historical review receipt exists. Source-only or synthetic results
must never display Run readiness; Cluster Mutation Not Admitted remains.

**Activation boundary:** current registration/update deliberately persists
`enabled=false`. #5461 separates explicitly scoped local inventory preparation
and committed historical readback from runtime admission: a checked active
source-only record with explicit false execution/mutation flags may prepare
non-executable inventory through the existing local KV v2 CLI. Provider TLS,
independent cluster/mount/token scope, exact topology and immutable CAS/readback
remain mandatory. No enable flag changes or execution are authorized. The
normal inventory builder, `diagnose_remote_preflight_target` and
`dispatch_kubespray_plan_review` continue to require an enabled connection.
The runtime activation contract remains outstanding under #4799/#5172.
Do not manually set `enabled`, insert evidence, or use local review flags
as execution authority.

In the local workspace terminal (replace the IDs with actual canonical
connection and actor IDs; do not use a production environment):

```bash
flask --app run:app automation-remote-review-check --help
APP_ENV=development KAORI_LOCAL_AUTOMATION_SECURITY_REVIEW=1 \
  KAORI_LOCAL_REMOTE_PREFLIGHT_REVIEW=1 \
  flask --app run:app automation-remote-review-check \
  --connection-id CONNECTION_ID --actor-id ACTOR_ID
```

The operator evaluates an existing actor; this does not authenticate or
impersonate that actor, create approvals, enqueue jobs, or write evidence.
The command returns a nonzero status on the first blocker. It always says
execution_authorized=false. It requires the actual application configuration
to be development and PostgreSQL READ COMMITTED, and rolls back its transaction.

| Result | Next check |
| --- | --- |
| local_review_disabled | Local review flags and actual APP_ENV |
| committed_review_unavailable | Local DB/migrations/transaction availability |
| actor_permissions_unqualified | Explicit persisted role membership and credential-use permission |
| connection_unqualified | Active enabled Ansible connection |
| source_not_checked | Exact committed source validation |
| ee_digest_unqualified | Committed immutable EE digest |
| topology_unqualified | Exactly 1 control-plane and 2 distinct worker/host members |
| host_registry_unqualified | Canonical non-production host scope |
| inventory_receipt_unqualified | Historical provider KV v2 readback and pinned Ansible parser |
| access_review_unqualified | Each member's current local grant, remote draft, typed credential version evidence and independent SSH trust |
| historical_target_qualified | Target metadata review only; no native runtime or execution |

On an independently prepared local automation worker with the reviewed
candidate checkout and signed review authority files already mounted,
the same command with `--worker-check` additionally reads the configured
`KAORI_LOCAL_REMOTE_REVIEW_WORKER` and
`KAORI_LOCAL_REMOTE_REVIEW_SOURCE` and checks the exact disabled source
and externally signed receipt. It does not measure the worker image,
open SSH, retrieve credentials or produce a signature. The stock
Dev Container runServices do not start the dedicated automation worker;
do not repurpose another queue or treat a web shell as worker attestation.

## 4. End-to-end acceptance boundary

| Stage | Current review boundary | Required real UAT evidence |
| --- | --- | --- |
| Connection | Validated source registration / eligible same-ID edit | Fresh proof and stable canonical identity |
| Inventory | Registered host roles and local KV v2 review | Checked source-only preparation or independently enabled connection, exact 1+2 host scope, parser-qualified receipt |
| Access | Typed credential and SSH trust candidate | Independent provider authority, current version and host-key evidence |
| Worker | Historical signed review, disabled external source candidate | Independently admitted signed EE/runtime and fixed remote facts result |
| Preflight and Plan | Review-only committed gates | Current 8+2 gate evidence, immutable Plan, separate maker/checker approval |
| Run | Reservation/adoption primitives; native mutation dispatch not admitted | Authorized disposable target, change window, lock and one canonical Run |
| Verify and bind | Independent observer primitives | Real Kubernetes API, required health and canonical Cluster binding |
| Completion | #5172 stays blocked until all stages pass | Human acceptance, exact-head Developer Check and Full Admission |

Source-only and local historical review do not prove an actual remote run.
Do not request operator acceptance for a partial stage as if it were the
complete lifecycle. External source PR `OXY7O/kaori-operations#10` remains
subject to independent review and admission; the review-only candidate does
not grant a native execution caller.

## 5. Evidence to return

Capture the exact KAORI SHA, migration current/head, focused pytest
summary, first diagnostic blocker, and screenshot of the selected
workspace/Remote Preflight Review state. Do not send provider tokens,
private keys, credentials, signed authority payloads or host access
details in chat.

Actual remote facts, full technical preflight, Plan/Run, cluster
registration and recovery UAT remain blocked by independent authority,
signed EE/worker admission and approved disposable target. External
kaori-operations PR #10 is a disabled candidate. No review flag, source
QA or diagnostic result enables native remote execution or provisioning.


## Workspace visual review (#5157)

The shared Violet Hero now uses its canonical context card, with truthful
connection count, review mode and setup action. Connection selection is a
separate registry from lifecycle posture, inventory and execution history.
Source, technical/governance gate counts and review-only Plan occupy three
ordered status cards; remote review sits next to those cards. The full-width
host registry remains independently paginated. Provider inventory evidence
and cluster associations are peers below it. No new execution controls.

No Ansible connection is a normal onboarding state (Setup Required), not
a workspace authorization failure. A filtered zero result instead shows
No Matching Connections, retaining the canonical filter/footer. No
selected lifecycle detail is rendered without a selected connection.
The page remains permission-scoped, GET-only, and committed-state based.
Review all states on desktop and mobile, Violet light/dark, keyboard and
HTMX/no-JS; visual acceptance is pending.

Observed preceding operator evidence: 181 tests passed and one encrypted
OpenSSH fixture failed before reaching the credential qualifier because
the test environment lacked the optional bcrypt dependency. #5456 adds
that dependency to the existing development manifests. The earlier run
is still a failure, and must be repeated before claiming PASS.


## Tabbed workspace revision (#5157)

The shared server-owned Framed Workspace Tabs separate Overview,
Connections, Inventory, Lifecycle and Executions immediately below the
Hero. Overview is global committed counts, with no selected connection
or provider I/O; inventory and execution counts respect existing
permissions. The selected scope is carried by URL across operational
tabs and can be changed through the paginated Connections registry.
Review opens Lifecycle; host enrollment/edit/retirement returns to
Inventory. Only the selected tab renders; lifecycle retains technical
gate details and remote review evidence. Mutation is still not admitted.
No new execution workflow or migration. Validate empty/filtered
connections, permission-restricted totals, back/forward and direct URL,
tab selection, host pagination, responsive and dark-mode visual review.


## Capability-first estate revision (#5157)

The top-level automation workspace uses the same Content Tabs,
Operational Section Card and Resource Posture Grid components as Kubernetes
Tenant. Overview is unscoped estate totals, a profile catalog, bounded
source attention (latest five connections) and recent canonical job
activity (jobs.view required). Counts are registered records, not
readiness. Profiles exposes the current Kubernetes Lifecycle workspace
and noninteractive planned Linux Hosts, Middleware & Database and
Network Automation. The existing connection registry and Readiness &
Plan are nested profile views; old URLs remain valid. Inventory and
Runs & Evidence keep explicit selected connection scope. No new provider,
profile admission, mutation or migration is introduced. The current
read model still supports only the approved Ansible/Kubespray profile;
future profiles require their own admitted adapters and workstreams.


## Foundation-aligned navigation (#5157)

The integrated server-owned workspace menu precedes the shared Hero; both
are inside the same HTMX replacement boundary. Foundation #556 defines
Overview, Hosts, Inventories, Profiles, Patching, Plans, Runs, Schedules
and Compliance. Hosts and Inventories are grouped; Runs includes evidence.
Existing connection registry stays under Profiles; legacy lifecycle and
executions URLs remain valid. Patching (IA-10/#4802), Schedules (IA-11)
and Compliance (IA-12) are explicitly read-only roadmap pages, not empty
operational registries or execution admission. Profile catalog remains
separate from Overview, with current Kubespray review and planned Linux
Hosts, Middleware & Database and Network profiles. Source registration
remains in Integrations. No new operation, provider or mutation authority.


### Shared Hero semantic pilot (#5398)

Infrastructure Automation uses the canonical execution-boundary status badge
`Not Admitted` with separate source-registration and independent approval
metrics. A registered source never grants execution authority. With an existing
connection, the Hero opens the exact Ansible registry using the shared
`Open Ansible Integrations` navigation action. Without a registered source,
the Overview/Connections setup state owns registration; the Hero explains the
prerequisite. Check both states, keyboard focus, light/dark and phone layout
in DevContainer before protected admission.
