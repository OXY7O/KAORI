# KAORI — GitHub App Source Control Dev Container UAT

Status: **Candidate only — not human accepted or released**.
Authority: #559, SC-01 #2740, SC-02 #2741, SC-03 #2742; authorization #724.
Branch: `kaori/review/staging-uat`. Official CI/CD remains **HOLD**.

## 1. Local-only admission

The shared temporary UAT aggregation branch now includes the reviewed SC-01/SC-02/SC-03 workstreams and makes the GitHub provider `available` for Dev Container testing. Other Vault/Notification Channels workstreams on this holding branch remain intact. SC-01/SC-02/SC-03 issue work branches and official Draft PRs retain the `planned` lifecycle until formal admission.

Use ignored local APP_ENV=development configuration, never a committed secret file:

- No UAT enable environment variable is required. The shared holding branch's `available` provider matrix enables GitHub directly. Credential registration and installation-specific operations still require an active local super-admin with `integrations.manage` until #724 is admitted.
- `SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=false` — leave HTTP webhook disabled until authenticated signature/replay negatives are reviewed.
- `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED=false` — leave maintenance inbox consumer disabled until worker/crash recovery is reviewed.

Restart Flask, Celery workers and Beat after local flag changes. Register the GitHub App PEM and webhook secret exclusively via KAORI's encrypted form; never place bearer tokens, PEM or raw payloads in JobExecution, logs, committed files or reports.

## Navigation for review

In the Dev Container running this UAT branch, sign in as an active local super-admin and open **Integrations → Source Control → GitHub**. The primary sidebar catalog and active-page/breadcrumb ownership reuse KAORI's existing Integrations navigation; no custom menu was added. GitHub is immediately available for registration and review without `SOURCE_CONTROL_GITHUB_UAT_ENABLED`.

If the new entry is not visible, verify that the running web container uses branch `kaori/review/staging-uat`, restart the Flask web process after checkout, and verify the user has `integrations.manage`. Source Control has now been integrated into `kaori/review/staging-uat` using a reviewed conflict-resolved merge commit. No branch named `kaori/staging` or `main` was changed.

## 2. Existing Developer Check — commands to run

To update the shared holding branch without discarding other reviewed UAT workstreams:

```bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
```

GitHub App review does **not** require `SOURCE_CONTROL_GITHUB_UAT_ENABLED`; continue keeping the webhook ingress and consumer disabled during initial testing.



```bash
git branch --show-current
git status --short
python scripts/verify_migration_graph.py
python scripts/verify_definition_registry.py
python scripts/verify_integration_domain_navigation.py
python scripts/verify_celery_topology.py
python scripts/verify_template_dependencies.py
python scripts/verify_python_syntax.py
python -m ruff check app/source_control app/models/source_control.py app/integrations/source_control tests/unit/test_source_control_*.py tests/ui/test_source_control_*.py
python -m ruff format --check app/source_control app/models/source_control.py app/integrations/source_control tests/unit/test_source_control_*.py tests/ui/test_source_control_*.py
python -m pytest -q --tb=short tests/unit/test_source_control_*.py tests/ui/test_source_control_*.py
python -m pyright --project pyrightconfig.json
bash scripts/quality_gate.sh --static
```

These are **not evidence of execution**. Use existing Developer Check planner and widen gates when migration, shared Kernel/Flask bootstrap or security boundaries change. Record exact SHA, failures and remediation evidence.

## 3. Database migration (controlled)

Never use normal app credentials for Alembic; never reset the PostgreSQL volume. Use approved Dev Container migrator per `docs/DEVELOPMENT.md` from the supported host directory:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
```

Expected revision chain: `20261023_scope_policy_storage → 20261023_channel_retire → 20261023_sc_identity → 20261023_sc_app_credential → 20261023_sc_webhook_delivery → 20261023_sc_repo_collection → 20261023_sc_webhook_job_link`.

The pre-existing `20261023_channel_retire` Alembic parent is retained byte-identically from this holding branch. The Source Control migration children were added after this approved parent. Verify upgrade/downgrade on an explicitly disposable PostgreSQL database, not user data.

## 4. Worker preflight

Existing queues: `inventory` (GitHub sync), `integration-validation` (Full Validation), `integration-runtime` (health refresh) and `maintenance` (optional signed-webhook consumer). The registered job `source_control.repository.sync` policy and both webhook flags start **disabled**.

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
celery --app celery_worker:celery_app inspect registered
celery --app celery_worker:celery_app inspect active_queues
```

Check `app.integrations.source_control.tasks.sync_source_repositories` on the inventory worker and the existing validation task on its worker. Canonical JobExecution must reject dispatch when its exact worker is unregistered.

## 5. Full functional UAT

1. Open `/integrations/source-control/github/` and register a real, limited-permission GitHub.com App installation via the encrypted form. Confirm Test Connection does not fabricate inventory readiness.
2. Sign in as an active **local super-admin**, open `/integrations/source-control/github/uat/`, select an installation and run **Full Validation**. Observe canonical JobExecution and require metadata + Contents read for connection readiness.
3. Run **Sync Repositories**, follow canonical JobExecution progress and review `/integrations/source-control/github/uat/installations/<record-id>`. Verify default 5-row pagination (5/10/25/50), HTMX, loading/empty/error state and light/dark/responsive design.
4. Test Unknown before complete collection versus a provably empty installation, All/Selected grants, rename/transfer/archive, access-lost-not-deleted, stale-generation ordering and retention of committed inventory after partial/rate-limit errors.
5. Confirm exact SHA plus observation timestamp from a native-ID-qualified default-branch check. SHA collection is bounded to 20 refs/run: missing/unchecked SHA must be Unknown and job partial, not full-history completeness.
6. Repeat using an independent GitHub App installation under a **second organization**. Prove no cross-installation repository leak. Ordinary users and SSO administrators must be denied from the UAT workspace.
7. Review keyboard/accessibility, mobile/tablet/desktop layout, dark/light themes, masked credentials, worker failure states and notification feedback.


The UAT inventory table polls committed KAORI state every 15 seconds via the installation-scoped HTMX GET route; it does not call GitHub. The installation detail now shows the latest five signed delivery receipts, correlation to canonical JobExecution, and recovery state, without raw payloads. Registration and UAT views are restricted to local super-admins until #724 is admitted. Revision gaps count every eligible repository even though only 20 default-branch tips are requested per run.

Recent Jobs on the GitHub installation detail must contain only canonical
Source Control Full Validation / Runtime Refresh for that exact connection or
Repository Sync for that exact installation. An unrelated JobExecution sharing
`scope_key=installation:<id>` must never appear as GitHub evidence (see #3021).
The UI still shows only the five most recent qualifying jobs. Verify this
negative case with `tests/unit/test_source_control_github_job_evidence_scope.py`.

## 6. Signed webhook (separate controlled UAT)

Only after local HMAC/replay negatives pass, opt into `SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=true`; HTTP 202 is a **committed delivery receipt**, never successful source reconciliation. Test no/malformed signature, wrong installation, UUID replay/collision, oversized body, rate limit and revoked App.

Only after worker/recovery review, opt into `SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED=true`. Test queued/partial/failed/canceled terminal JobExecution mapping, 5-minute preclaim backoff, three-attempt review, ambiguous-dispatch quarantine, and retention of previous committed repository scope after failure. Never expose the Dev Container publicly or point a production GitHub App to it without network/security approval.

## 7. Acceptance evidence and release boundary

Collect SHA, migration graph and DB upgrade/downgrade, `ruff`/`pytest`/`pyright`/`djlint`/verifiers, queue registration, two redacted real installation scopes, JobExecution IDs/status, HMAC negative results and UI screenshots in both themes. Record FAIL and remediation separately. **Human acceptance is mandatory** for this user-visible and security-sensitive integration.

The code is assembled on the shared **temporary** `kaori/review/staging-uat` holding branch for Dev Container UAT. No merge to official `kaori/staging` or `main`, no official CI/CD admission and no production flags until explicit authorization.
