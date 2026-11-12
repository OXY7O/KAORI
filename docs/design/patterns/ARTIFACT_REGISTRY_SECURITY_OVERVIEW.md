# Artifact Registry Security — Overview and focused workspaces

## Authority and scope

- Parent capability: #896. Bounded visual/route implementation: #4468.
- Existing sync and finding-state governance: #948, #915.
- Reference presentation: the approved Artifact Registry Inventory Overview and KAORI shared design patterns (#946, #4455, #572, #753).
- Operational source of truth: **committed KAORI Registry security evidence**, not a live Harbor/scanner query. External scanner/provider remains authoritative for detection, signature and SBOM evidence.

## Navigation and ownership

| Route | Endpoint | Purpose |
| --- | --- | --- |
| `/artifact-registry/security` | `artifact_registry.security_overview` | Read-only Security Overview landing |
| `/artifact-registry/security/vulnerabilities` | `artifact_registry.security` | Existing Vulnerabilities workspace and canonical finding filters |
| `/artifact-registry/security/supply-chain` | `artifact_registry.security_supply_chain` | Existing Supply Chain workspace with capability and evidence subviews |

The sidebar Security capability links to the Overview. The shared `workspace_navigation_catalog.py` now owns the three top tabs **Overview → Vulnerabilities → Supply Chain**, rendered by `layouts/app.html` via `components/workspace_tabs.html`. Do **not** duplicate tab markup in Security templates.

Existing internal `url_for('artifact_registry.security')` and `url_for('artifact_registry.security_supply_chain')` continue to target their original focused workspaces; their route **paths** may differ from historic Security entry URLs. Every route uses `artifact_registry.view` authorization. The Overview `source_id` is validated through the existing fail-closed Security source resolver; Overview catalog links preserve the validated ID.

## Overview composition

1. KAORI Violet shared Hero: source/critical/affected context, source-qualified risk posture, direct action to Vulnerabilities.
2. Shared **Security Evidence Snapshot** context bar: freshness, eligible Registry scope, usable scan coverage and exceptions; a successful job is **not** equivalent to current committed scan evidence.
3. **Security Workspaces** catalog: two compact shared `workspace_link_card` destinations, derived critical-finding and signature/SBOM coverage-gap counts.
4. **Security Evidence Posture**: shared `operational_section_card`, `N Indicators` metadata label, and four compact `resource_posture_grid` metrics for critical, high, affected artifact digests and correlated runtime bindings.

The Overview projection reuses `_registered_sources`, `_providers`, `_security_scope_evidence`, `_security_scope_labels`, `_security_snapshot_context`, and `_security_posture`. Counts and tones use committed-scoped evidence only. When no current successful scan evidence is present, metric tones are **Unknown** rather than inferred Healthy from zero counts. This does not certify absent findings, non-exposure or supplier compliance. Unsupported signatures/SBOM are not presented as verified.

When providers are unregistered or committed inventory is not ready, retain the existing shared provider/inventory blocked states and standard corrective navigation.

## Security Evidence Operations copy

On focused Vulnerabilities and Supply Chain pages, `_security_sync_live_state.html` displays a **single concise line** combining a source-qualified queued/syncing/failed/not-collected/ready state with **read-only; no provider scans**. It must wrap naturally on narrow viewports; never truncate or use `nowrap`. Progress, polling, disable-duplicate execution, Jobs & Executions authority, and the canonical `artifact_registry.security.sync` job remain intact.

## QA and admission

- Exact-commit djlint and Ruff check/format on updated templates and Python files.
- Focused Security source contract and navigation contract, existing RBAC/scope regression, and current dashboard verifier where applicable.
- Browser Visual UAT of 1440/1280/mobile widths in light/dark, keyboard focus and tab navigation, active source/blocked/no evidence/stale/partial evidence, and sync status transition. Record screenshots under issue #4468.
- The temporary `kaori/review/staging-uat` holding integration is **not** official Full Admission; `kaori/staging`, main, deployment and release remain gated by Human Acceptance.
