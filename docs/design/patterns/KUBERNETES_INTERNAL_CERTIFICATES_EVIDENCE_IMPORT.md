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

## 3. Controlled Dev Container import

Confirm the database target, review backup/restore and migration plan and ensure the input file is a restricted, redacted **metadata-only** manifest. Apply the database revision **before** using the new read model:

```bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
flask db heads
flask db current
flask db upgrade
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

After a successful import and refresh:
- `Kubernetes → Governance → Internal Certificates` shows the committed **Internal Certificate Registry** with default 5/page, cluster/node/component, kind, issuer, source-reported `NotAfter`, externally managed flag, evidence reference/collection time, status and source coverage.
- The status is one of **Expired**, **Critical Window** (within 7 days), **Renewal Window** (within 30 days), **Outside Window**, or **Stale Evidence** (metadata older than 30 days). These are **display classifications of operator-reported expiry**, not verified active health. Expiry windows are provisional display thresholds pending policy approval, not automation triggers.
- Empty/unsupported/permission denied/migration gap remain distinct from healthy; an empty inventory never produces a green success indicator.
- **Source Readiness** changes to **Operator Attested** only when a source batch exists. Authority remains explicitly **Operator Supplied**, and renewal stays deferred.
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
| Renewal request | No action available until Ansible/governed workstream #4445 is approved |

## 6. Validation and acceptance

Run existing quality gates, focused importer/read-model/route tests, schema upgrade and downgrade in a disposable database, and Visual UAT light/dark/mobile. Test unauthorized users get 403, no secret-bearing query, HTMX search/page changes, a pilot with at least 6 approved certificate records to prove page 2, and duplicate/older/invalid imports.

**Human acceptance requires actual non-production source evidence.** The code path can be reviewed without it, but the operational requirement “certificate values visible” is not complete until a real authorized source is imported and verified in Dev Container. Keep #4443/#4444 OPEN; no PKI renewal or host mutation is implemented here.

Related: [Source Contract](KUBERNETES_INTERNAL_CERTIFICATES_SOURCE_CONTRACT.md), [Deferred Renewal Blueprint](KUBERNETES_INTERNAL_CERTIFICATES_RENEWAL_BLUEPRINT.md), #4461, #4443, #4444, #4445.
