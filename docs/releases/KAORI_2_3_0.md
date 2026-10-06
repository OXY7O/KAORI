# KAORI 2.3.0 Release Notes

**Release date:** 2026-08-18
**Git tag:** Pending (`v2.3.0` after final approval)
**Release type:** Minor release
**Status:** Pre-tag release candidate; tag and publication require the full final gate in the canonical Dev Container

## Summary

KAORI 2.3.0 advances the 2.2 release baseline into a provider-neutral operational platform release. The main scope is the Integration lifecycle redesign, Object Storage/MinIO analytics and lifecycle alignment, stronger Platform Operations and Automation Control boundaries, Identity Provider hardening, and release metadata/documentation cleanup.

The release also closes pre-tag regressions detected during final review, including an Identity Providers Jinja import failure and unresolved runtime/type symbols reported by Ruff.

## Release Focus

### Provider-neutral Integration lifecycle

- Prometheus and Thanos remain implementations of the canonical Metrics Source category rather than separate consumer abstractions.
- Prometheus and Alertmanager own consumer-binding mutation; Kubernetes and MinIO asset-owner lifecycle views remain read-only evidence surfaces for those bindings.
- MinIO follows the same managed-provider lifecycle shape as Kubernetes: registration, connection test, Core Validation, runtime refresh, configuration, consumer evidence, and guarded deletion.
- Consumer profiles keep Kubernetes/Object Storage metric and alert validation asset-scoped so a shared source does not become globally degraded by one consumer.

### Object Storage and worker-owned analytics

- Object Storage Forecast uses persistent worker refresh snapshots instead of browser-request calculation.
- Metrics and alert dependencies remain provider-neutral and binding-scoped.
- Data Lifecycle, Jobs & Executions, notification delivery, and archive/storage evidence stay within shared Platform Operations contracts.

### Access, Identity Provider, and release hardening

- Identity Provider workspace ownership remains separate from user lifecycle and adapter implementations.
- The release fixes the Jinja component import used by `/access/identity-providers/` and adds a regression contract for that canonical import.
- Remaining Ruff `F821` defects in Automation Control, TLS Governance, and Protected Secret Reveal are resolved by restoring the canonical type/runtime imports.
- The Pyright release gate is closed through typed SQLAlchemy construction, ORM-compatible RBAC policy signatures, typed report/analytics payload boundaries, and runtime adapter/recovery contract alignment.
- Type analysis also caught and fixed the Object Storage `provider_key_key` typo plus stale `record=` calls in Integration Validation recovery/binding refresh paths.
- Release metadata, running/testing documentation, compatibility presentation, and release-governance references are synchronized to 2.3.0.

## Compatibility

KAORI 2.3.0 distinguishes **upstream version freshness** from **KAORI-qualified compatibility**. The qualified matrix in **Settings → General Settings → Compatibility Versions** is the application policy and still requires live capability evidence.

Recommended qualified baselines for this release:

- Kubernetes: v1.36.x
- Prometheus: v3.13 LTS
- Alertmanager: v0.33.x
- Thanos Query: v0.42.x
- MinIO: `RELEASE.2024-08-03T04-33-23Z` (exact qualified release)

The Thanos compatibility catalog adds an explicit `thanos-query-v0-42` profile. MinIO is now shown in System Information as a release-identifier contract rather than being omitted from the compatibility catalog.

## Upgrade Notes

1. Back up PostgreSQL.
2. Deploy the immutable `v2.3.0` image and keep `APP_VERSION=2.3.0`.
3. Validate the production environment.
4. Apply all migrations through the current release head.
5. Start web, Beat, and the canonical dedicated workers.
6. Re-run provider Core Validation / binding validation where the release changed Integration contracts.
7. Confirm Settings → General Settings → System Information reports KAORI 2.3.0 and the expected build SHA/date.

See `docs/RUNNING.md`, `docs/DEPLOYMENT.md`, and `docs/deployment/RELEASE_GOVERNANCE.md` for the canonical commands and approval boundary.

## Release Verification

The prepared source must first pass the dependency-light release ownership gate:

```bash
python scripts/verify_final_release.py
```

A local annotated release tag may be prepared for handoff after that source-level gate. **Do not push or publish the tag** until the canonical Dev Container/runtime environment passes the complete gate:

```bash
python scripts/verify_final_release.py --all --runtime
```

Publication is approved only when the complete command ends with:

```text
PASS — KAORI Final Release
```

Verify that the annotated tag points at the exact release commit:

```bash
git show --no-patch --decorate v2.3.0
```
