# KAORI Quality and Architecture Gates

## Purpose

KAORI uses mandatory release gates to prevent behavior regressions, import-cycle failures, architecture drift, migration divergence, generated artifacts, and duplicated UI implementation before a production image is published.

Kubernetes Operations adds `verify_kubernetes_operations_final_lock.py` to the static phase. The verifier freezes AuthZ-first cluster prerequisites, Full-Width Mutation Workspace v2 ownership, retired content-rail absence, and L0–L7 permanent evidence for ConfigMap/Secret CRUD.

Access adds `verify_access_final_lock.py` to the same static phase. The verifier freezes the read-only Access overview, explicit user/role/provider permission boundaries, last-super-admin and stale-write protections, bounded remember-me persistence, authentication actor-versus-target audit semantics, Activity Audit ownership, shared modal/tab/table composition, and the reviewed Access UI debt ceiling.

Authentication adds `verify_authentication_surface_final_lock.py` to the static phase. The verifier freezes the compact Login and Database Setup Required surfaces, safe redirect/session/cookie invariants, generic credential-failure semantics, SSO state/nonce/TTL ownership, accessible form controls, KAORI Violet compact-login geometry, external first-party interaction runtime, and the reviewed authentication UI debt burn-down.

The concise general release entrypoint is:

```bash
python scripts/verify_final_release.py
```

It first proves that all current sidebar/navigation surfaces and registered Flask blueprints have explicit release ownership. The canonical registry is `scripts/release_surface_registry.py`; `scripts/verify_release_surface_coverage.py` fails when a menu link, menu template, Blueprint, verifier, or evidence path is unowned. The current contract covers 62 navigation links and 27 registered blueprints, including non-navigation Authentication, Notification Center, Runtime Health, and nested Cluster Management ownership under Integrations → Kubernetes.

For the complete release gate use:

```bash
python scripts/verify_final_release.py --all
```

Add `--runtime` when live worker/runtime readiness must also pass. Successful general-runner output is deliberately compact (`PASS — KAORI <Area>`); failed steps retain complete child diagnostics. `scripts/quality_gate.sh` remains the canonical phase implementation used by CI and is also callable directly.

The release workflow calls the same gate through `.github/workflows/quality.yml`. A production image must not be published until every required phase succeeds.

## Gate Structure

### Static and Architecture Gate

```bash
bash scripts/quality_gate.sh --static
```

This gate performs, in order:

1. Source hygiene validation, including source archives that do not contain `.git` metadata.
2. Release-surface coverage validation: every navigation endpoint and registered Blueprint has an explicit owner, verifier/evidence boundary, and lock state.
3. In-memory Python syntax compilation without generating `__pycache__` or `.pyc` files.
4. Strict Ruff linting.
5. Ruff formatting verification.
6. djLint validation for Jinja templates.
7. Pyright type and import analysis.
8. Architecture dependency-boundary validation.
9. Internal module and imported-symbol resolution.
10. Runtime import-cycle detection, excluding imports guarded by `TYPE_CHECKING`.
11. Application-module reachability validation.
12. Celery task, route, queue, worker, and Beat topology validation.
13. Code-health debt-ceiling validation.
14. Alembic revision-graph validation.
15. Test location and marker-taxonomy validation.
16. Reviewed-domain release-test coverage validation across Unit, Functional, Integration, Security, Rendering/UI, and E2E evidence.
17. Jinja syntax, reusable UI boundary, and inline-debt validation.
18. Architecture and migration contract tests.

### Functional Gate

```bash
bash scripts/quality_gate.sh --tests
```

The broad test run executes every permanent non-E2E test except temporary diagnostics:

```bash
pytest -q -m 'not debug and not e2e'
```

Reviewed domain characterization suites that actually exist are invoked explicitly, and the critical smoke layer runs separately:

```bash
pytest -q tests/welcome tests/access tests/integrations tests/kubernetes/dashboard tests/kubernetes/analytics tests/kubernetes/inventory tests/kubernetes/governance tests/kubernetes/operations tests/storage tests/platform_operations tests/reports tests/settings -m functional
pytest -q tests/e2e -m e2e
```

Settings is protected by `scripts/verify_settings_final_lock.py`, which locks authenticated preference ownership, `system.view` gating for safe release metadata, CSRF-protected browser-timezone synchronization, Account credential/session semantics, canonical General/Account workspace composition, retired side-context cleanup, and zero page-local palette/arbitrary-typography regressions. Reviewed-domain static ownership is also explicit. Kubernetes Inventory is protected by `scripts/verify_inventory_final_lock.py`, which validates AuthZ-before-readiness ordering, committed-snapshot/provider boundaries, canonical Hero/table/modal/pagination composition, Topology database ownership, zero residual Inventory helpers/files, documentation ownership, and the permanent L0–L7 evidence manifest. The same verifier is invoked by `quality_gate.sh` and the core Kubernetes final lock.

Intelligence is protected by `scripts/verify_intelligence_baseline_lock.py`, with `scripts/verify_automation_control.py` locking the Automation Control cockpit and default-deny execution boundary. This remains a **baseline** lock rather than a declaration that every Intelligence provider/action is feature-complete: Intelligence Overview, Recommendations, Rule Catalog, and supported Alert Intelligence read/evidence surfaces are active; Automation Control governance preparation is operational, while infrastructure execution defaults to **Governance Only / Execution Disabled** through `AUTOMATION_EXECUTION_ENABLED=false`. The controlled Kubernetes Deployment restart lifecycle requires candidate materialization, maker-checker governance where applicable, scoped deployment policy, readiness/safety admission, one-time authorization, server-side dry-run, canonical worker execution, post-action verification, recovery evidence, audit, and notification delivery. Server/HCI providers and additional automation actions still require their own runtime/security/E2E evidence before promotion.

Separating E2E keeps the smoke boundary visible in CI while avoiding duplicate execution in the broad test run. E2E smoke is deterministic by default: it exercises real Flask routing/session/template/application-shell composition while isolating external persistence/provider dependencies unless the test explicitly provisions them. PostgreSQL, Redis, S3, Kubernetes, Prometheus, and Alertmanager semantics belong to Integration tests. Explicit domain characterization protects core behavioral evidence from environment-level marker configuration or `PYTEST_ADDOPTS`. `scripts/verify_feature_test_coverage.py` must never list planned/nonexistent tests; add a domain requirement only when that evidence is committed during its final recheck.

### Frontend Gate

```bash
bash scripts/quality_gate.sh --frontend
```

This performs a clean dependency installation, Prettier verification, local runtime-asset generation, Tailwind CSS compilation, and generated-asset verification:

```bash
npm ci --no-audit --no-fund
npm run check-format
npm run build-frontend
npm run verify-frontend
```

Runtime CDN dependencies remain prohibited.

## Test Taxonomy

One hook in `tests/conftest.py` owns path-based marker assignment. The release strategy is intentionally layered:

| Layer | Location / command | Marker | Release role |
| --- | --- | --- | --- |
| Static Quality | `quality_gate.sh --static` | n/a | Syntax, lint, format, type, architecture, migration graph, UI/source hygiene |
| Contract Test | `tests/contracts/` | `contract` | Durable ownership and invariant evidence |
| Unit Test | `tests/unit/` | `unit` | Isolated deterministic logic |
| Functional Test | `tests/<domain>/` | `functional` | User-visible/domain behavior |
| Integration Test | `tests/integration/` | `integration` | Component/provider/infrastructure collaboration |
| Security Regression | `tests/security/` | `security` | AuthN/AuthZ/disclosure/input/privileged-operation regression |
| Rendering/UI Contract | `tests/rendering/` | `rendering` | Jinja/frontend/document/UI composition |
| End-to-End Smoke | `tests/e2e/` | `e2e` | Critical real-application smoke journeys |
| Migration Test | `tests/migrations/` | `migration` | Upgrade/downgrade/data transformation |
| Debug | `tests/debug/` | `debug` | Temporary reproduction only; excluded |

Nested `conftest.py` marker hooks are prohibited. A defect may begin with a debug reproduction, but it must finish with permanent evidence in the correct layer before the debug test is removed. A final-recheck page may use `N/A` for Unit or Integration only with a written architecture justification.

## Import and Initialization Safety

KAORI validates three separate import properties:

1. Every internal module exists.
2. Every explicitly imported top-level symbol is defined or re-exported by its target module.
3. The runtime import graph is acyclic.

This is designed to detect missing implementation files, stale re-exports, partially initialized modules, and circular imports before pytest collection or application startup.

## Ruff Zero-Debt Policy

KAORI does not use a Ruff diagnostic baseline. The canonical checks are:

```bash
python -m ruff check app migrations tests scripts
python -m ruff format --check app migrations tests scripts
```

Rules:

1. Every configured Ruff diagnostic blocks the static gate.
2. New and existing files receive the same enforcement.
3. Unused imports must be removed rather than retained as compatibility hints.
4. Import blocks must remain deterministic and grouped by standard library, third-party, and first-party imports.
5. Historical Alembic revisions retain only narrow per-file exemptions for import ordering and annotation modernization.
6. Suppression comments require a specific rule code and an operational reason.

## Architecture and Code-Health Debt

The machine-readable ledgers are:

```text
docs/architecture/architecture-debt-baseline.json
docs/architecture/code-health-debt-baseline.json
```

They are ceilings, not quality targets. A listed cycle, form dependency, broad exception, large module, or large function may shrink or disappear, but it may not expand. A resolved entry must be removed from the baseline in the same change.

The code-health ledger is additionally checked by `scripts/verify_code_health_baseline_integrity.py`. The verifier keeps the default 800/160/30/8 ceilings immutable and requires every debt exception to equal the currently measured value exactly, so the baseline cannot contain hidden growth allowance.

New code should follow:

```text
HTTP / CLI / Celery Adapter
        ↓
Application Use Case
        ↓
Domain Contract
        ↓
Provider or Repository Adapter
```

The following are enforced:

- models cannot depend on request globals, routes, or forms;
- task modules cannot import routes or forms;
- services cannot import routes;
- wildcard imports are prohibited;
- retired compatibility, shim, and empty placeholder modules cannot return;
- imports targeting retired modules remain prohibited after deletion;
- application modules must have an importer, configured runtime entrypoint, test consumer, or script consumer;
- route modules may only be imported by application or package bootstrap modules.

## Domain Namespace and Metrics-Source Boundary

`scripts/verify_domain_namespace_architecture.py` enforces direct-cutover domain
ownership for Inventory and Analytics. It rejects retired import paths and
filesystem namespaces instead of permitting compatibility packages. It also
requires Object Storage Analytics to consume the provider-neutral
`MetricsSource` contract through a qualified asset-provider + metrics-provider
adapter and blocks retired product/provider aliases. The same verifier locks the
`PLATFORM OPERATIONS → Operations Center` navigation distinction.


## Reusable UI Boundary

Dynamic progress widths are centralized in:

```text
app/templates/components/progress_bar.html
```

Templates outside that component may not use inline `style=` attributes. `scripts/verify_ui_reuse.py` also parses every Jinja template, rejects local `<style>` blocks, and prevents inline scripts or event handlers from increasing beyond the recorded burn-down baseline.

`scripts/verify_ui_style.py` prevents page-local style drift from increasing. Its per-template ceiling covers arbitrary typography and radius values, raw palette usage, semantic-border review candidates, custom compact labels, custom hero titles, repeated standard surface shells, copied right-context geometry, and page-local workspace tablists. The counts are review candidates rather than blanket defects; they must decrease during page-by-page standardization and the baseline must be updated in the same change.

The remaining inline-script, event-handler, and style-drift baselines record existing debt only. New UI work must prefer shared Jinja components, semantic tokens, Alpine behavior, HTMX attributes, and static frontend modules.

## Migration Governance

`scripts/verify_migration_graph.py` validates:

- revision IDs are unique;
- every parent revision exists;
- revisions cannot reference themselves;
- the graph has exactly one root;
- the graph has exactly one head;
- the graph contains no cycle.

This static gate complements database upgrade and downgrade tests; it does not replace them.

## Source Archive Policy

Do not ZIP a working directory. Use:

```bash
bash scripts/build_source_archive.sh
```

The script requires a clean Git checkout and creates the archive with `git archive`. Cache directories, compiled bytecode, local runtime data, secrets, generated reports, and nested ZIP files are rejected. When a source archive is audited without `.git`, the hygiene gate scans the entire archive rather than skipping validation.

## Development Completion Checklist

Every logical change must finish with:

```text
code
→ smallest applicable Unit/Functional/Integration/Security regression tests
→ relevant Contract/Rendering/Migration evidence
→ critical E2E smoke when the user journey or application shell changes
→ documentation and changelog review
→ static, test, and frontend gates
→ git diff review
→ dedicated Git commit
```

- Kubernetes Governance final recheck: `verify_governance_final_lock.py` plus Unit, Functional, Integration, Security, Rendering/UI, E2E, and Governance Contract evidence are mandatory after the domain is reviewed.
