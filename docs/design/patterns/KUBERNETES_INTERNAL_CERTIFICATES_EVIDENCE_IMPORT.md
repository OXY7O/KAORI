# Kubernetes Internal PKI — Operator-Attested Metadata Import

> **Scope:** An interim, controlled evidence-ingestion path for #4461 / #4443 until approved host-side Ansible orchestration and provider-qualified collection are available. **Not an automated collector or renewal engine.** The Kubernetes API alone cannot establish control-plane host-local `kubeadm` certificate expiry.

## Authority and data boundaries

- Use **source-qualified**, approved, non-production pilot evidence first. Confirm the source is kubeadm-managed by the cluster owner; do not infer that from an API version or cluster status.
- This command commits **only validated certificate metadata**: source version, registered cluster ID, exact control-plane node, component/CA type, issuer, UTC validity interval, externally-managed indicator, coverage declaration and change/evidence reference.
- The source and issuer values are **operator attested**, not independently cryptographically verified by KAORI. Valid `not_after` does **not** prove that a node currently uses this certificate, that clients trust its CA, or that automatic renewal is safe.
- No private keys, signing keys, PEM certificate bodies, CSR bodies, kubeconfigs, raw `kubeadm` stdout, machine credentials, arbitrary shell commands, source filenames, or external provider secrets are persisted.
- Only the existing operator who controls the KAORI deployment and PostgreSQL access should invoke the CLI; **do not** expose import as an HTTP route. The source record is linked to an immutable evidence batch and an Activity Audit event without raw payloads.
- A later per-host collector must reuse/extend the committed normalized contract, not replace the provider's PKI authority or execute renewal from the page.

## 1. Approved source collection (outside KAORI)

On a **confirmed kubeadm** control-plane node, an authorized operator obtains the version and expiry data through the installed native tooling and an approved maintenance/operational process:

```bash
sudo kubeadm version -o short
sudo kubeadm certs check-expiration -o json
```

The Kubernetes CLI output format is **version-dependent**. Do not pipeline arbitrary JSON from this command directly to KAORI. Review the version-specific output fields, identify the named node and CA/leaf source, exclude credentials and map the public expiry metadata into the strict manifest below. If the source is custom, provider-managed or externally issued without a verified mapping, **do not import** as kubeadm.

If no approved source identity is available, stop at **Not Collected / Not Verified**. Do not scrape `/etc/kubernetes/pki` recursively, read CA private keys, or run root shell from a KAORI web request.

### Docker Desktop Kubernetes — local pilot source qualification

Docker Desktop Kubernetes may use **kubeadm** (single-node) or **kind** (multi-node). The host workstation shell and the Dev Container shell are **not** the Kubernetes control-plane node. Therefore `sudo: kubeadm: command not found` on a host such as an X300 is **not** evidence that the cluster lacks a kubeadm-based provisioner, nor evidence that its host-local PKI can be collected. The Kubernetes distribution/provider identity remains unverified until the user checks Docker Desktop **Kubernetes → Edit cluster** and records the actual provisioner.

Non-mutating discovery on the **workstation with the intended kubectl context**:

```bash
kubectl config current-context
kubectl config get-contexts
kubectl --context docker-desktop get nodes -o wide
kubectl --context docker-desktop get pods -n kube-system -o wide
```

Run the context-specific commands **only if** the intended test context is `docker-desktop`. If the context is different, do not silently switch or probe an unrelated cluster. These API results establish cluster identity/nodes, **not** active apiserver, etcd or kubelet certificate `NotAfter` values. Never infer source authority just from a pod name or image.

- **Docker Desktop / kind**: Docker Desktop/kind owns the cluster lifecycle. A generic kind report is **not supported** by the kubeadm-only v1 manifest. **However**, the operator has now verified `kubeadm v1.36.4` inside `desktop-control-plane` and the exact `output.kubeadm.k8s.io/v1alpha3` report; the narrowly version-locked, metadata-only adapter below can normalize *this specific kubeadm source* after owner review. This does **not** grant CA/renewal authority or make kind a kubeadm-managed provider.
- **Docker Desktop / kubeadm**: native provisioning may use kubeadm under Docker Desktop's managed control plane, but `kubeadm` is not expected to run on the workstation. An owner-approved control-plane-local, version-qualified, **read-only** source is still required before constructing the strict kubeadm manifest. Do not `docker exec` into infrastructure containers or mount control-plane paths just to bypass permission controls.
- Docker Desktop manages its own Kubernetes lifecycle. **Never attempt to renew, overwrite or rotate its control-plane/etcd PKI from KAORI**, and do not use `kubeadm certs renew` as a Docker Desktop operational playbook. For a disposable local cluster, lifecycle/reset actions remain under Docker Desktop ownership and need separate human approval because reset may discard local workloads/resources.

Reference: [Docker Desktop Kubernetes provider/provisioner documentation](https://docs.docker.com/desktop/use-desktop/kubernetes/). The `#4442` source support matrix and `#4445` native-renewal ownership decision define the provider boundary; the current view reports source metadata, not verified active PKI expiry.

## Verified Docker Desktop control-plane report — v1.36.4 pilot (2026-11-12)

The operator has now demonstrated an **actual read-only source observation** for
`docker-desktop` from the local non-production control-plane container:
`docker exec desktop-control-plane kubeadm version -o short` returned
`v1.36.4`, and `kubeadm certs check-expiration -o json` returned
`CertificateExpirationInfo / output.kubeadm.k8s.io/v1alpha3`, with
**11 leaf/kubeconfig entries and 3 CAs**. Reported expiry is 11 September
2027 for most leaf entries, 12 November 2027 for apiserver, and 8 September
2036 for the CAs. Source file observation does **not** cryptographically prove
active certificate installation or authorize rotation. The PKI tables were previously empty. On 2026-11-12 the operator imported the reviewed 14-record batch `107855b3-8f8b-407a-84fe-9bdf7e75be38` into the development database and verified 11 leaf + 3 CA inventory rows and Activity Audit. **This remains operator-attested UAT metadata, not automated collection or proof of installed/active certificate use.**

Docker Desktop may use the **kind** cluster provisioner even when its
`desktop-control-plane` node has a functional **kubeadm** binary. These are
different facts: the provisioner remains Docker Desktop/kind, while the
accepted *metadata source tool* is kubeadm. **KAORI never acquires Docker
Desktop lifecycle/renewal authority** from this read-only observation.

### Prepare an actual manifest, review, then commit through existing CLI

A bounded, version-qualified adapter is available **only** for
`kubeadm v1.36.4` and the **exact** report schema
`output.kubeadm.k8s.io/v1alpha3`. It rejects unexpected fields,
unsupported/missing components, duplicate entries, unknown CA references,
malformed timestamps, unknown source versions and credential-bearing keys.
It translates only the supported public expiry/issuer/externally-managed
metadata; `residualTime` is discarded and `not_before` remains `null`
because this report does not supply it. It cannot create new keys, restart
components, or contact the cluster.

**Capture from the already-authorized local pilot source** using the
verified `docker-desktop` context on the operator's WSL workstation.
Capture time must correspond to the same *new* report; do not invent it
from this chat or assume the original report's exact timestamp:

```bash
kubectl config current-context   # Must be docker-desktop
umask 077
EVIDENCE_DIR="$(mktemp -d -t kaori-pki-uat.XXXXXX)"
COLLECTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker exec desktop-control-plane kubeadm version -o short
docker exec desktop-control-plane kubeadm certs check-expiration -o json > "$EVIDENCE_DIR/report.json"
printf 'Collected at %s; private source directory: %s\n' "$COLLECTED_AT" "$EVIDENCE_DIR"
```

This creates a temporary source file **outside Git**. The user must
review that the target is their intended local cluster and that the report
has only metadata (never private keys, kubeconfigs, PEM or CSRs). Do not
generalize `docker exec` to production, nor use it as a KAORI web/worker
collection path. The operator explicitly authorizes local source access;
the adapter itself performs **no Docker or SSH execution**.

Copy only the reviewed metadata source file to the **actual Dev Container**
under a private temporary path by the operator's approved local file-transfer
workflow (e.g. `docker cp` after verifying the workspace container ID).
Do not place either the raw source or the prepared manifest under
`/workspace/kaori` or commit it to Git.

Find the correct registered **KAORI Cluster UUID** from the already
migrated Dev Container DB; `docker-desktop` is a *kubectl context name*,
**not** the required UUID:

```bash
flask db current  # Must be 20261112_internal_pki (head)
flask shell
# Inside the Python shell:
# from app.models.cluster import Cluster
# [(cluster.id, cluster.name, cluster.environment) for cluster in Cluster.query.order_by(Cluster.name).all()]
# exit()
```

In the Dev Container, protect the output location and prepare a candidate
manifest **without any database write**. Replace the marked values with the
actual cluster UUID, UTC capture timestamp printed above, and the
operator's own evidence/change reference; the following paths are illustrative:

```bash
mkdir -p /tmp/kaori-pki-evidence
chmod 700 /tmp/kaori-pki-evidence

flask prepare-internal-pki \
  --input-file /tmp/kaori-kubeadm-report.json \
  --output-file /tmp/kaori-pki-evidence/reviewed-manifest.json \
  --cluster-id '<REGISTERED-KAORI-CLUSTER-UUID>' \
  --node-name desktop-control-plane \
  --source-version v1.36.4 \
  --collected-at '<UTC-CAPTURE-TIMESTAMP>' \
  --reference UAT-DD-PKI-20261112-001 \
  --coverage-state partial
```

The converter creates its target file with **0600** mode, refuses
overwriting an existing path and refuses writing into the repository.
`partial` is intentionally the safe default until the operator
independently verifies that the reported 14 components form a
complete source scope. The `--reference` above is an illustrative UAT
evidence ID, **not an asserted approved production change ticket**.

**Review the resulting JSON**: exactly 14 allowlisted metadata records
(11 leaf/kubeconfig, 3 CA), correct CA associations, real source
`expirationDate`, `not_before: null`, `externally_managed` flags,
correct cluster UUID/node, and trusted operator reference. The converter
does not query or assert the active runtime certificate chain.

Only after the reviewed UAT manifest matches the actual source and
database target, invoke the already-approved import path:

```bash
flask import-internal-pki --input-file /tmp/kaori-pki-evidence/reviewed-manifest.json
# Expected on success: records=14, status=operator-attested (with batch UUID).
```

Confirm counts using **read-only** SQL against the same verified Dev Container
database or the existing Flask application shell, and review the
`Kubernetes → Governance → Internal Certificates` workspace with
`cluster_id` correctly scoped. The registry uses **5 results per page**;
14 imported source reports should occupy **three pages**. Expiration is
displayed as **source reported**, not active certificate verification.
Keep the batch ID and redacted count as UAT evidence, then dispose of
temporary raw/manifest files through the operator's approved process.
No secrets or source reports are attached to GitHub issues.

The importer remains unchanged and authoritative: strict v1 manifest,
registered UUID, source-qualified deduplicated upsert, Activity Audit,
and no mutation on validation failures. #4443 approved Ansible read-only collection remains a separate future workstream. #4445 confirms renewal stays with the native Kubernetes platform or external PKI owner; KAORI renewal is not planned.

## 2. Strict, metadata-only manifest

The following is a **schema example, not production evidence**. Replace every sample value from a verified source; UTC timestamps must be timezone-aware and the `cluster_id` must match an actual UUID registered in KAORI. `reference` identifies the approved change/evidence ticket and must not contain credentials.

```json
{
  "schema_version": "kaori.internal-pki-evidence.v1",
  "cluster_id": "00000000-0000-4000-8000-000000000001",
  "node_name": "control-plane-example",
  "source_kind": "kubeadm_check_expiration",
  "source_version": "v1.31.0",
  "collected_at": "2026-11-12T09:00:00Z",
  "coverage_state": "partial",
  "reference": "CHG-EXAMPLE-001",
  "certificates": [
    {
      "component": "apiserver",
      "kind": "leaf",
      "issuer": "ca",
      "not_before": null,
      "not_after": "2027-11-12T09:00:00Z",
      "externally_managed": false
    },
    {
      "component": "ca",
      "kind": "ca",
      "issuer": null,
      "not_before": null,
      "not_after": "2036-11-12T09:00:00Z",
      "externally_managed": false
    }
  ]
}
```

Supported components are intentionally restricted to kubeadm's known control-plane/etcd leaf certificates and CA names, such as `apiserver`, `apiserver-kubelet-client`, `apiserver-etcd-client`, `etcd-server`, `etcd-peer`, `etcd-healthcheck-client`, `front-proxy-client`, `controller-manager.conf`, `scheduler.conf`, `admin.conf`, `ca`, `etcd-ca` and `front-proxy-ca`. Kubelet active client/serving certificate validity **cannot** be asserted with this kubeadm input. Preserve `externally_managed: null` when not verified.

The validator rejects unknown keys, invalid UTC timestamps, duplicate components, inconsistent CA/leaf classification, unknown types, oversized source files and mismatched cluster identities. A `complete` manifest replaces the complete known inventory for the exact cluster+node+source; use `partial` until completeness has been verified. A failed validation commits nothing. A repeated normalized manifest is idempotent; older evidence cannot overwrite a newer committed snapshot.

### Preflight the `db-bootstrap` Python image before any privileged PKI schema upgrade

During the 2026-11-12 local UAT, the operator-only migrator passed
`PASS: trusted, non-superuser migration identity admitted`, but Flask
could not import `run:app` because the running `db-bootstrap` image lacked
the **already-locked** `qrcode` package. As a consequence, `flask db`
was unavailable and **no schema migration completed**. This is distinct
from the earlier `kaori_runtime` schema `CREATE` privilege denial.

Follow the **canonical DevContainer** image rebuild and Python import
preflight in
[devcontainer-postgres-first-run.md](../../operations/devcontainer-postgres-first-run.md)
before the separately authorized `--upgrade-only` operation. The one-shot
Compose service is built from the Dockerfile `development` stage and must
contain base dependencies (including `qrcode==8.2`); do not install
dependencies manually in a throwaway container or disable MFA. The
preflight only verifies software availability, not the database schema.

### PostgreSQL migration permission failure — use the **existing KAORI privileged migration service**

**Canonical authority:** [DevContainer PostgreSQL first-run & upgrade](../../operations/devcontainer-postgres-first-run.md) (#1427, merged #1462), `scripts/devcontainer/bootstrap-db.sh`, and the existing [least-privilege contract](../../../tests/contracts/release/test_devcontainer_postgres_runtime_role_contract.py). These **supersede generic DBA GRANT instructions for the KAORI DevContainer**.

The operator's `flask db current` showed `20261025_bot_protection` and `flask db heads` showed `20261112_internal_pki`. Direct `flask db upgrade` inside the workspace failed at `CREATE TABLE internal_pki_evidence_batches` with `permission denied for schema public` **by design**: normal Flask runs as restricted `kaori_runtime`, which **must not have schema CREATE privilege**. `flask seed-rbac` independently succeeded (5 roles / 68 permissions), but did not advance Alembic or create PKI tables.

**Do not attempt to fix the failure with schema grants to `kaori_runtime`, an ad-hoc DBA login, copying migration credentials into the container, `flask db stamp`, or a volume reset.** Instead, for a reviewed local `kaori-dev` UAT schema upgrade, run the **existing one-shot Compose service from the host's checkout root**, preferably native Windows PowerShell when WSL/OneDrive secret-file permissions differ:

```powershell
# Non-mutating Compose configuration/secret-file preflight.
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml config --quiet

# Operator-authorized migration + post-DDL runtime grants/RBAC/ledger checks.
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
```

The service consumes the scoped protected `secrets/devcontainer/postgres-migrate.env` credential, validates the exact `kaori-dev` database and `kaori_migrator` owner, runs Alembic under the ephemeral **`KAORI_DB_MIGRATION_URL`**, refreshes restricted **`kaori_runtime`** grants (including immutable Capsule protection), seeds RBAC without recreating the first admin, then validates runtime admission. `--upgrade-only` does not reset or delete PGDATA. The existing `db-first-run` service **must not** automatically migrate an already-initialized schema.

After successful operator execution, inspect `flask db current` from the regular Dev Container runtime and confirm **`20261112_internal_pki (head)`** plus both actual PKI tables, with redacted migration logs. A migration failure remains a blocker; do not treat the newly seeded permission or an empty inventory as evidence of a successful schema upgrade. If the one-shot runner fails its ownership, credential, grants or Capsule guard, investigate the specific gate in the canonical runbook instead of bypassing it.

**Deployment boundary:** the above is **DevContainer-only**. For server/VM or external DBA-managed PostgreSQL, use [production governed migration authority](../../operations/postgres-dba-migration-contract.md), not DevContainer migration secrets or this Compose service.

## 3. Controlled Dev Container import

Confirm the database target, review backup/restore and migration plan and ensure the input file is a restricted, redacted **metadata-only** manifest. Apply the database revision **before** using the new read model:

```bash
# In Dev Container, inspect schema state only (non-mutating):
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
flask db heads
flask db current

# Do NOT run `flask db upgrade` with the restricted workspace DATABASE_URL.
# First execute the canonical host-side db-bootstrap --upgrade-only command
# above, then verify the schema is current:
flask db current

# Only with approved non-secret source metadata and completed PKI migration:
flask import-internal-pki --input-file /secure/operator-reviewed/internal-pki-evidence.json
```

The input path above is an **example**, not a file created by KAORI. Do not commit the manifest to Git, upload it to a public issue, or paste raw host output into a PR. The CLI emits only evidence batch ID, count and `operator-attested` status.

**Migration and import are UAT DB changes.** Never run them against production without explicit environment/backup/change approval. A migration is not a certificate renewal and has no Kubernetes host-side effects.

## 3A. Verify above-Hero Governance navigation and inventory scope (Dev Container)

The page-level **Overview · TLS Certificates · Internal Certificates** tabs are rendered by the
existing `layouts/app.html` and `workspace_tabs.render_navigation` component **above the
Hero**. They are permission-aware. A user without at least two authorized detailed views
will not receive a tab row; do not duplicate it inside the page template.

After the approved staging-UAT checkout and database migration, explicitly reconcile
the canonical role permissions in the **intended Dev Container database**:

```bash
flask db current
flask seed-rbac
```

`flask seed-rbac` mutates the selected database and should never be run blindly against
production. It is **not** invoked by an HTTP GET. Verify the user has
`governance.view`, `clusters.view`, and `internal_certificates.view` to access
Internal Certificates; `tls_certificates.view` controls the TLS tab separately.
Custom roles must be reviewed and updated through existing Access workflows.

In **Internal PKI Source Registry**, select a registered cluster using **View PKI
Evidence**. The URL retains `cluster_id` for this page's committed certificate
inventory; **Clear Cluster Scope** returns to all clusters. Search and default
five-row pagination remain scoped to the selected cluster, and the total committed
source-reported certificate count must not display another cluster's count.

If `flask db current` shows an unapplied internal PKI schema revision, apply the
approved migration before import; `Inventory Schema Upgrade Required` is distinct
from `No internal certificate evidence is committed`.

**Evidence for UAT:** record exact git SHA, selected DB environment, migration state,
RBAC seed result, a screenshot of the three authorized tabs **above** the Hero, a
screenshot of a cluster-scoped certificate registry after a real approved import,
and the redacted evidence batch ID. Never attach raw kubeadm stdout or keys.

## 4. Read-only UI and expected states

The approved Internal Certificates layout follows the already-admitted TLS
operational composition: **above-Hero capability tabs → Hero → Internal PKI
Collection Snapshot → Internal PKI Collection Operations → Certificate Posture
→ Internal PKI Evidence tabs**. The evidence section uses the same canonical
`workspace_tabs.render_query_tabs` server/HTMX interaction as Artifact Registry
CVE Evidence, with **Registered Source Coverage** (default) and **Certificate
Inventory** (on demand) in one workspace panel. `View PKI Evidence` opens the
certificate tab scoped to the selected cluster, and browser navigation retains
each tab's independent search/page/rows parameters. It reuses canonical
`snapshot_context_bar`, `action_button`, `operational_section_card`, and
`resource_posture_grid` components. The original **PKI Evidence Boundaries**
explanation remains an Info Tip on Collection Operations, not a redundant
full-size card or standalone Source Readiness heading.

The snapshot text deliberately uses concise, complete one-line copy
(`PKI evidence is committed; active use is unverified.`, `Collection time in UTC.`,
`Coverage is unverified.`) within the existing compact shared context bar;
meaningful source detail remains in the registry, Info Tip and audit metadata.

The snapshot and posture are derived from **committed KAORI inventory/batch
rows**. The latest source report is a source-capture timestamp in UTC, **not**
a successful automated worker run. The scope follows the selected cluster
(or all clusters); indicators aggregate the whole scoped committed inventory,
not just the current five-row table page. Six posture indicators show reported
Outside Window, Renewal Window, Critical Window, Expired, Stale Evidence and
Partial Evidence. Partial Evidence counts records from source batches explicitly
marked partial; it is not an independently verified cluster-wide completeness
assessment. Reported expiry does not establish actual in-use certificate health.

**Sync Internal PKI is intentionally disabled** (button with no form/action or
HTMX mutation endpoint). Until #4443 and the approved #556 Ansible read-only
collector are admitted, operations show `Not Configured`, `No Worker Runs`,
and `Not Scheduled`. Operator-attested import does not populate automated run
fields. Schema missing or no committed source displays **Not Assessed / Not
Collected**, not fabricated zero-health or success. Kubernetes and PKI providers
remain authoritative for renewal outside KAORI.


After a successful import and refresh:
- `Kubernetes → Governance → Internal Certificates` shows the committed **Internal Certificate Registry** with default 5/page, cluster/node/component, kind, issuer, source-reported `NotAfter`, externally managed flag, evidence reference/collection time, status and source coverage.
- The status is one of **Expired**, **Critical Window** (within 7 days), **Renewal Window** (within 30 days), **Outside Window**, or **Stale Evidence** (metadata older than 30 days). These are **display classifications of operator-reported expiry**, not verified active health. Expiry windows are provisional display thresholds pending policy approval, not automation triggers.
- Empty/unsupported/permission denied/migration gap remain distinct from healthy; an empty inventory never produces a green success indicator.
- **Source Readiness** changes to **Operator Attested** only when a source batch exists. Authority remains explicitly **Operator Supplied**; renewal is native platform/PKI-owned, not deferred KAORI execution.
- Existing TLS Secrets / Ingress coverage remains a separate capability; no blending of counts or identities.

## 5. Failure and recovery

| Condition | Expected response |
|---|---|
| No admitted source | No import; Not Collected |
| Unknown cluster | Reject with no write |
| Unknown component, key/PEM-like fields, invalid UTC | Reject before transaction |
| Duplicate source manifest | Return existing batch without duplicate audit/rows |
| Older source timestamp | Reject; preserve latest committed evidence |
| Partial inventory | Preserve other existing records; label coverage Partial |
| Complete verified inventory | Replace absent rows for the exact cluster/node/source only |
| New migration not applied | UI shows **Inventory Schema Upgrade Required**, never invents an empty healthy inventory |
| Failed database write | Roll back batch, rows and audit together |
| Source older than 30 days | Keep evidence; mark Stale Evidence |
| Renewal request | Not supported in KAORI; follow the native platform or PKI owner's approved procedure outside KAORI |

## 6. Validation and acceptance

Run existing quality gates, focused importer/read-model/route tests, schema upgrade and downgrade in a disposable database, and Visual UAT light/dark/mobile. Test unauthorized users get 403, no secret-bearing query, HTMX search/page changes, a pilot with at least 6 approved certificate records to prove page 2, and duplicate/older/invalid imports.

**Human acceptance requires actual non-production source evidence.** The code path can be reviewed without it, but the operational requirement “certificate values visible” is not complete until a real authorized source is imported and verified in Dev Container. Keep #4443/#4444 OPEN; no PKI renewal or host mutation is implemented here.

Related: [Source Contract](KUBERNETES_INTERNAL_CERTIFICATES_SOURCE_CONTRACT.md), [Native Renewal Ownership](KUBERNETES_INTERNAL_CERTIFICATES_RENEWAL_BLUEPRINT.md), #4461, #4443, #4444, #4445.
