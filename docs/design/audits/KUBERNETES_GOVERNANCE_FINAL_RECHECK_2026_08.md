# Kubernetes Governance Final Recheck — August 2026

## Scope

Reviewed Kubernetes Governance Overview and TLS Certificate Governance against the KAORI Engineering Standard v1 without redesigning the accepted workspace.

## Findings

1. Blueprint-level clusterless handling could respond before route-level RBAC. The blocker is retired; TLS routes now authorize first and evaluate readiness inside the protected request path.
2. `get_active_tls_sync_job()` had no runtime/test/script caller and is removed instead of retained as compatibility surface.
3. TLS collection retains the data-minimization boundary: only `tls.crt` is decoded for inventory; `tls.key` is never read by the collector. Mutation scrubs live Secret and encoded upload payloads.
4. Existing canonical UI remains: shared Hero, Status Badge Box / Context Icon Box, shared table/status/pagination, Full Workspace Modal, operational progress toast, Notification Deck and Activity Audit delivery.
5. Governance now has permanent L0–L7 release evidence and a final-lock verifier wired into the release gate.
6. TLS wildcard host coverage is explicitly single-label: `*.example.com` covers `api.example.com` but not deeper names such as `deep.api.example.com`.
7. The standalone validity-policy test restores every temporary `sys.modules` package entry after loading certificate policy code, so Governance functional-test collection cannot be poisoned by a fake `app` package.
8. TLS Governance UI follow-up consolidates `TLS Inventory Operations` into `Certificate Validity & Operations`, aligns TLS detail-modal status placement with the shared Inventory header contract, and converts single TLS rotation to a full-width integrated workspace without the retired right context rail.
9. Single TLS rotation now uses three cohesive sections: compact target/posture evidence, combined certificate-pair upload plus embedded validation actions, and combined controlled flow plus Governance posture handoff.

## Performance and reliability

The registry paginates rows in SQL with the canonical default 5 and options 5/10/25/50. Sync is dispatched through canonical Jobs/Celery ownership with overlap control, retries, user-scoped progress status, terminal Activity Audit, and Notification Deck evidence. Web reads do not mutate Kubernetes.

## Database and migration

No schema change is required by this final recheck. Existing TLS inventory/collection/update-event migrations remain authoritative and the global single-head migration gate remains mandatory.

## Verdict

**TARGETED FIX — AUTHORITATIVE VALIDATION PENDING** until the devcontainer Static Quality, L0–L7 suites, browser smoke, and full release gate pass.

### Single TLS rotation density refinement

The full-width rotation workspace was compacted after browser review to avoid large unused visual regions. `Target TLS Secret` now uses a three-column identity strip followed by a bounded Current TLS Posture header, four compact metrics, and an Issuer/Fingerprint technical row. This replaces the earlier target/posture split, which left unused space and made long fingerprints wrap excessively. `Controlled Rotation & Governance Posture` renders the four-step flow full-width and follows it with one horizontal evidence strip for status, Days Remaining, Host Coverage, and the Certificate Details handoff. The previous large flow/posture side-panel split is explicitly retired and guarded by contract/verifier checks.

### TLS Certificate Detail evidence workspace

The Certificate Detail composition was rebuilt as `evidence-workspace-v2`. The shared detail partial still serves both the registry Full Workspace Modal and the direct-link page, but it now has only three primary sections: `Certificate Identity & Validity`, `Coverage & Consumer Evidence`, and `Collection & Governance`. The previous independent identity, validity, coverage, collection, certificate-identity, and rotation-handoff cards were removed to reduce card nesting and vertical whitespace. Host Coverage Matrix remains the detailed relationship evidence table, while collection state and the controlled rotation handoff are consolidated into one Governance footer.

