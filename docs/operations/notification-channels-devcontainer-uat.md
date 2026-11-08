# KAORI — Notification Channels Dev Container UAT Evidence Matrix

**Authority:** #1429 / #2872; reliability #1431, #1475, lifecycle #2847–#2850.
**Branch:** `kaori/review/staging-uat`. **Official CI/CD admission: HOLD.**
**Operator statement:** Functional Notification Channels UAT **Accepted** on
2026-10-23 for paths personally tried. This is not blanket evidence for
every provider, worker crash, data-retention or security scenario.

## Exact tested candidate

| Field | Record |
| --- | --- |
| Worktree branch | `kaori/review/staging-uat` |
| Exact local Git SHA tested | **PENDING — record `git rev-parse HEAD`** |
| Merge/PR provenance | #2866 provider retry, #2871 lifecycle safety contract; pre-existing UI/provider PRs in #1429 |
| Dev Container Flask/PostgreSQL/Celery versions | **PENDING** |
| Alembic revision after authorized migration | **PENDING** |
| Source/target provider credentials/scope | **PENDING — record identifier only, no secrets** |
| Test scenarios and screenshots/log evidence paths | **PENDING** |
| Operator functional UI sign-off | **ACCEPTED** (scope of manually tested functionality, 2026-10-23) |
| Provider failure-injection, lifecycle, security, database UAT | **NOT RUN / NOT VERIFIED** |
| Reviewer / re-review date | **PENDING** |

Never copy a private token, webhook URL, raw provider payload, or encrypted
replay envelope into the evidence file or GitHub issue.

## Refresh and quality gates (local only)

```bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD
git status --short
python scripts/verify_migration_graph.py
python scripts/verify_python_syntax.py
python scripts/verify_notification_channels.py
python -m ruff check app/integrations/delivery/notification_channels app/models/notification_channel.py
python -m ruff format --check app/integrations/delivery/notification_channels app/models/notification_channel.py
python -m pytest -q --tb=short \
  tests/contracts/integrations/test_notification_retry_after_contract.py \
  tests/contracts/integrations/test_notification_channels_audit_20260817_contract.py \
  tests/contracts/platform_operations/test_data_lifecycle_notification_delivery_archive_contract.py \
  tests/contracts/intelligence/test_alert_operations_lifecycle_contract.py
```

These commands are *planned gates*, not proof that anyone ran them. If the
migration verifier finds multiple heads or errors, **stop**, do not stamp,
reset, force-head or modify another branch.

### Controlled database upgrade — Dev Container only

The persisted `next_retry_at` field from #1475 requires revision
`20261023_notify_retry_after`, followed by the **inert**
`20261023_delivery_identity` schema (#2868). The second revision does not
backfill identity rows or activate any new runtime path. Reuse the approved separate
migration identity from `docs/operations/github-source-control-devcontainer-uat.md`
and `docs/DEVELOPMENT.md`:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
```

Run **only** against the explicitly prepared local Dev Container database.
Verify Alembic current/head and source replay afterward. Do not use normal
Flask app credentials for upgrade or deploy to staging/prod.

## Scenarios / Gherkin evidence slots

Each scenario must record exact SHA and environment, expected/actual,
PASS / FAIL / BLOCKED / NOT RUN, timestamp and a redacted evidence locator.

| ID | Scenario | Expected result | Evidence state |
| --- | --- | --- | --- |
| NCH-UI-01 | Overview, Details-first Channel Actions, Retire/Archived, Delete Locked | Authorized actions and dialogs; guarded history; responsive + keyboard + dark/light | **Functional UAT accepted**, individual matrix NOT PROVIDED |
| NCH-UI-02 | Delivery Activity filters, pagination 5, Retention Policy link | Normal/HTMX GET; canonical lifecycle URL; permission-gated link | **Functional UAT accepted**, negative RBAC proof NOT PROVIDED |
| NCH-PROV-01 | Telegram / optional Forum Topic valid/invalid | Target topic when approved; invalid topic fails closed; GitHub Actions notifier separate | **NOT VERIFIED per scenario** |
| NCH-PROV-02 | SMTP/Email positive/negative, TLS/auth failure | Correct provider ack; no credential echo | **NOT VERIFIED per scenario** |
| NCH-PROV-03 | Teams Workflow allowed host, redirect/invalid URL | Approved HTTPS only, no unsafe redirected secret send | **NOT VERIFIED per scenario** |
| NCH-PROV-04 | ntfy on approved owned on-prem endpoint/CA | Approved topic + TLS/trust; no SSRF or auth disclosure | **NOT VERIFIED per scenario** |
| NCH-PROV-05 | Slack/Discord 2xx/429/invalid/timeout | Typed bounded Retry-After, redacted URLs, safe mention behavior | **NOT VERIFIED per scenario** |
| NCH-RETRY-01 | HTTP 429 seconds/date/malformed/capped | Provider delay persisted only when approved; global floor preserved | **NOT RUN** |
| NCH-RETRY-02 | Retry worker restart, two concurrent SKIP LOCKED claims | No early due claim; at-least-once unknown acknowledged accurately | **NOT RUN** |
| NCH-RETRY-03 | Reconfigured/retired channel or rotated credentials | Stale replay rejected with no outbound send | **NOT RUN** |
| NCH-LIFE-01 | Data Lifecycle paused/manual archive-only Preview | Only aged sent/skipped; failed/queued protected | **NOT RUN** |
| NCH-LIFE-02 | Verified JSONL.GZ/manifest/archive checksum | No credentials/replay/raw errors; evidence stays hot | **NOT RUN** |
| NCH-LIFE-03 | Force archive-and-cleanup at policy/API/engine | **DENY**, no hot data deleted | **NOT RUN** |
| NCH-AUDIT-01 | One business action, multiple channel fan-out/retries | Delivery evidence does not manufacture Activity Audit rows | **NOT RUN** |
| NCH-SEC-01 | No permission/tenant source scope + malformed provider inputs | Redacted, no leaked event/source data or transport | **NOT RUN** |
| NCH-PERF-01 | Large journal, scoped filters and outcome aggregation | Bounded query latency; no fabricated archived totals | **NOT RUN** |

Provider sends are allowed only to explicitly owned UAT destinations and
after verifying target, credentials, scope, and environment. For
retry/failure-injection, use controlled mock provider and test database.
Keep `NOTIFICATION_DELIVERY_RECOVERY_ENABLED=false` by default.

## Known issue dependencies / STOP conditions

- #2850, #2868, #2869, #2870: hot cleanup and archive record lookup **NOT
  ADMITTED**; current archive-only policy may not reduce PostgreSQL size.
- #1475 / PR #2866: source integrated, database migration and worker
  failure-injection still pending; do **not** enable recovery on source review.
- #1458/#1459/#1460/#1454/#1473: adapters are registered, but per-provider
  negative/security evidence has not been recorded.
- #2345/#2357: Source Control outbound events still require authoritative
  committed source workflow evidence, not GitHub Actions Telegram side effects.
- #1220: exact business audit producer coverage is partial; do not equate
  provider acknowledgment to read/human receipt or audit completion.

**Exit:** a reviewer records per-case outcome, screenshots/redacted logs,
exact branch and SHA, schema revision, job/provider readiness and human
approval. Only then may the relevant issue be marked accepted; official
Developer Check/Full Admission remains a separately authorized next step.

### Ledger backfill candidate (separate safety workstream)

`app/integrations/delivery/notification_channels/identity_backfill.py`
contains an internal, preview-first bounded ID reconciliation helper for
#2868. It is intentionally **not** registered as a callable UI/API/Celery
job and should not be invoked against real data until the JobExecution
cursor/restart contract and PostgreSQL concurrent mutation tests are
reviewed. The high-watermark/cursor are external to this helper and do
**not** constitute a completed backfill certificate. An
`apply=True` call can commit database writes; use only approved disposable
DevContainer data and explicit authorization. The existing hot source
journal remains authoritative; no dedup cutover or cleanup is admitted.

Add an evidence record for preview counts, conflict/missing status,
duplicate insert/rollback, batch-size protection, concurrent writers,
resumption, and verification against the source identity on a disposable
PostgreSQL test database before progressing the issue.
