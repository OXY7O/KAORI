# Security Posture — cross-domain committed evidence

**Architecture authority:** #721 (Security Posture), #900 (Intelligence boundary), #747/#748 (Sidebar v2), #2600 (CVE-to-Application plan).  
**Initial implementation:** #2610. Pre-UAT hardening: #2613.

## Ownership

Security Posture is an Assurance workspace that **consumes** source-qualified committed evidence. It is not a second scanner, CMDB, secret store, SIEM, advisory service, recommendation engine or generic vulnerability database.

- **Artifact Registry** owns scanner CVE, package, version, digest and scan generation (initial source).
- **Kubernetes / Registry runtime correlation** owns observed workload bindings, source identity and signed input-generation readiness.
- **Central Intelligence** owns recommendation/alert/accepted-risk lifecycle. **Reports** owns publication.
- Later Security workstreams may add Source Control, Services/Team, Vault/PKI, hosts, Network and policy exceptions only after approved source and evidence contracts are available.

## Routes / navigation

- `/security/` → **Security → Overview**. Shared KAORI Operational Dashboard Hero profile, three source-qualified Operational Signal KPI cards and approved four-tab dashboard framework.
- `/security/findings` → **Security → Findings**. Server-backed grouped CVEs, scanner finding counts, distinct immutable artifact digest counts, existing Kubernetes binding counts, search/severity filters and 5/10/25/50 pagination.
- `Artifact Registry → Security` continues as authoritative source-domain workspace. Exact CVE rows link to its existing `/artifact-registry/security/cve/<CVE>/impact` drill-down; Security does **not** duplicate that detail view.
- The **Assurance** sidebar contains a two-level Security parent with only real route-backed Overview/Findings children. Planned capabilities remain hidden; no new renderer/CSS family.

## Read / RBAC contract

Both Security routes require `security_posture.view`; `flask seed-rbac` (in a configured **development** environment) registers the new canonical permission. **Artifact Registry source reads and source links additionally require** `artifact_registry.view`. A Security-only authorized user sees qualified unavailable/unknown states without any Registry SQL data access. Integration management and Intelligence/Reports links remain separately permission-filtered. Do not grant Registry visibility transitively from this aggregate parent.

The read model consumes only active/enabled Registry integrations with committed inventory. CVE rows come from the latest usable successful scanner snapshot per artifact. Failed scan refresh preserves last-good evidence, but freshness can become stale; a newer successful scan supersedes old findings. Deduplicated artifact and runtime binding counters are *observations* and are never a normalized application owner count. The oldest usable scanner observation and missing inventory scan coverage qualify scanner readiness; mixed partial/stale evidence is **Partial / Stale**. The canonical Runtime Correlation readiness reflects input changes and failures separately. Missing, unsupported, stale or denied sources must not be described as remediated or 'no exposure'.

The Findings registry differentiates **strong digest bindings** from weaker
**mutable/reference bindings** using the same correlation identity distinction
as Artifact Registry Runtime Usage. Binding counts reflect observed
container-level relationships, **not** a deduplicated count of logical
applications. No source-only 0 may be interpreted as remediated or all clear.

The initial result cannot speak for all Kubernetes workloads without matching source evidence, direct-host PHP packages, standalone Docker, network reachability, Service/Team ownership or global risk posture. No provider network I/O, mutation, new migration or background scan occurs from normal GET.

## Review and UAT

Use existing checks (no custom quality-gate framework):

```bash
ruff check app/security_posture app/bootstrap/blueprints.py app/common/navigation.py app/common/workspace_navigation.py app/common/workspace_navigation_catalog.py tests/contracts/security_posture
ruff format --check app/security_posture app/bootstrap/blueprints.py app/common/navigation.py app/common/workspace_navigation.py app/common/workspace_navigation_catalog.py tests/contracts/security_posture
djlint app/templates/security_posture/overview.html app/templates/security_posture/findings.html --check
pytest -q tests/contracts/security_posture/test_security_posture_workspace_contract.py tests/contracts/design/test_sidebar_navigation_standard_contract.py
python scripts/verify_sidebar_navigation_standard.py
```

Developer Check must include Jinja macro rendering tests, source-access negative tests, scanner-state cases and both Findings pagination directions. Human UAT must still verify active/sidebar collapse/mobile, 6 canonical viewports, light/dark, visible deep links, current/partial/stale/empty scanner data and no misleading zero/all-clear. Passing static tests alone does not satisfy human acceptance.
