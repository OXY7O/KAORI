# Kubernetes Lifecycle — Dev Container exploratory review

Authority: #5186, #4801, #5172 and #2227. This is a non-release review
workbench handover, not native host UAT or mutation admission. The existing
Operations Center workspace reads committed state.

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

## 2. Test the source-only vertical path without real hosts

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

Open Operations Center → Infrastructure Automation → Kubernetes Lifecycle.
Select an existing Ansible source connection. Check source, host registration
and inventory receipt. Under Recent Automation Executions, the Remote
Preflight Review block requires jobs.view and shows Not Recorded until
a real canonical review receipt exists. Source-only or synthetic results
must never display Run readiness; Cluster Mutation Not Admitted remains.

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

## 4. Evidence to return

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
