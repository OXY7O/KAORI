# KAORI 0.2.0 Release Notes

**Release date:** 2026-09-23  
**Git tag:** Pending (`v0.2.0` after governed stable promotion)  
**Release type:** Stable product-line release  
**Status:** Final release preparation; stable publication requires final exact-SHA RC, governed UAT, explicit acceptance, and digest-preserving promotion

## Summary

KAORI 0.2.0 consolidates the current product line around evidence-driven Kubernetes and Object Storage operations, provider-neutral integrations, Intelligence and Reports, governed delivery, responsive Violet UI standards, and an independently managed public-edge publication model.

This release also completes the post-UAT hardening program: integration compatibility qualification, environment/release governance, OCI supply-chain evidence, responsive Hero/mobile behavior, security warning disposition, repository hygiene, all-surface Visual QA, and reliable post-deploy shared-edge reconciliation.

## Release Focus

### Governed delivery and immutable release evidence

- Exact-source Developer Check and staging Full Admission remain the release admission authorities.
- Release candidates are built once, scanned, runtime/DAST verified, and bound to an immutable OCI digest.
- SPDX SBOM and SLSA provenance attestations are attached to the accepted digest.
- Stable promotion must reuse the exact UAT-accepted digest and must not rebuild application bits.
- Rollback and roll-forward boundaries preserve release-state, source, digest, and reviewed backup lineage.

### Provider-neutral operations and compatibility

- Kubernetes, Metrics Source, Alert Source, and S3-compatible Object Storage integrations retain provider-neutral KAORI contracts.
- Compatibility separates upstream version freshness, KAORI qualification, observed capability evidence, and consumer readiness.
- Normal operational surfaces continue to prefer committed KAORI state while explicit live validation remains provider-scoped.

### Responsive Violet UI and Visual QA

- The shared Hero contract owns concise action-oriented copy, canonical metadata density, and natural one-line non-phone rendering.
- Mobile navigation, Hero density, drawers, notification surfaces, tables, and dense content use responsive shared-component ownership rather than page-local device hacks.
- The governed Playwright Visual QA authority covers the canonical viewport matrix and representative light/dark authenticated surfaces.
- Human UAT remains required for user-visible acceptance and is not replaced by screenshot or geometry automation.

### Standalone public edge

KAORI application deployment and public-edge publication are separate lifecycles.

KAORI owns its application runtime and internal health. The standalone shared edge independently owns:

- host TCP 80/443;
- Nginx and Certbot;
- the `edge-public` Docker network;
- DNS/TLS/public readiness;
- ACME HTTP-01 and certificate lifecycle.

Post-deploy reconciliation safely publishes the current healthy KAORI web container through the existing shared-edge authority without moving Nginx/Certbot ownership back into KAORI Compose.

The operator procedure is documented in `docs/deployment/SHARED_EDGE_OPERATIONS.md`.

## Security and Supply Chain

- Gitleaks, Bandit, Semgrep, pip-audit, actionlint, Zizmor, ShellCheck, Hadolint, Trivy, and OWASP ZAP remain governed quality/security authorities.
- ZAP warning dispositions and SAST warning cleanup preserve fail-closed security policy rather than weakening gates.
- OCI annotations, immutable digest identity, SBOM/provenance attestations, and release verification preserve source-to-artifact traceability.
- Example/runtime packaging excludes real credentials and private production configuration.

## Operational Notes

### Upgrade / deployment

1. Back up PostgreSQL before a release transition.
2. Deploy only the governed immutable image/digest selected by release evidence.
3. Validate production environment authorities and migration readiness.
4. Apply migrations through the governed deployment adapter.
5. Verify PostgreSQL, Redis, web, workers, Beat, and internal readiness.
6. Reconcile standalone public-edge publication separately.
7. Verify public DNS, HTTP redirect, trusted TLS, readiness, Host/SNI rejection, and Certbot renewal.
8. Confirm **Settings → General Settings → System Information** reports the stable `APP_VERSION=0.2.0`, exact build SHA, and build date.

See:

- `docs/DEPLOYMENT.md`
- `docs/deployment/CI_CD_RECOVERY_CONTRACT.md`
- `docs/deployment/RELEASE_GOVERNANCE.md`
- `docs/deployment/SHARED_EDGE_OPERATIONS.md`

## Verification

Source and staging validation use the existing KAORI authorities:

```bash
bash scripts/quality_gate.sh --static
bash scripts/quality_gate.sh --tests
bash scripts/quality_gate.sh --frontend
python scripts/verify_release_governance.py
python scripts/verify_final_release.py --all --runtime
```

Final stable publication additionally requires:

- exact staging Full Admission;
- final immutable v0.2.0 RC;
- image vulnerability scan;
- production runtime and DAST evidence;
- SPDX SBOM attestation;
- SLSA provenance attestation;
- governed UAT deployment;
- explicit acceptance of the exact RC source SHA and immutable digest;
- stable promotion of the same digest;
- stable signature/tag/manifest verification.

## Deferred Major Domains

The following architecture/foundation epics are intentionally outside v0.2.0 implementation scope and remain subject to design discussion before implementation:

- Infrastructure Automation / Ansible (#556);
- Registry / Harbor (#558);
- Source Control / GitHub (#559);
- FinOps (#560);
- next-domain roadmap framework (#561).

Small fixes and narrowly scoped reliability corrections continue through the normal issue → branch → Developer Check → staging → admission path.

## Stable Publication Boundary

Do not manually create, move, or reuse the stable `v0.2.0` tag.

The stable release is complete only when the governed release workflow verifies the accepted RC source/digest lineage, promotes the same immutable digest, publishes the release manifest/GitHub Release, and confirms stable runtime identity.
