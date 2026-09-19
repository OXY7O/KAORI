# KAORI Test Taxonomy

KAORI separates evidence by purpose so a green test count cannot hide a missing security, rendering, migration, or end-to-end boundary.

| Layer | Location | Marker | Purpose | Release role |
| --- | --- | --- | --- | --- |
| Static Quality | `scripts/quality_gate.sh --static` | n/a | Ruff, Ruff Format, djLint, Pyright, JavaScript syntax, Prettier, architecture, code health, migration graph, source hygiene | Mandatory |
| Contract Test | `tests/contracts/` | `contract` | Durable architecture, ownership, canonical paths, UI invariants, retired boundaries | Mandatory supporting evidence |
| Unit Test | `tests/unit/` | `unit` | Isolated deterministic logic without application infrastructure | Required when a page/domain owns independent logic |
| Functional Test | `tests/<domain>/` | `functional` | User-visible/domain behavior, failure modes, application use cases | Primary behavior evidence |
| Integration Test | `tests/integration/` | `integration` | Collaboration across application components or infrastructure/provider boundaries | Required where such a boundary exists |
| Security Regression | `tests/security/` | `security` | Authentication, authorization, disclosure, input, secret, and privileged-operation regressions | Mandatory when a security boundary exists |
| Rendering/UI Contract | `tests/rendering/` | `rendering` | Jinja compilation, frontend structure, document rendering, accessible UI composition | Mandatory for user-facing pages |
| End-to-End Smoke | `tests/e2e/` | `e2e` | Critical application journeys through the real Flask/application stack; external infrastructure is isolated unless the smoke explicitly provisions it | Explicit deterministic release smoke gate |
| Migration Test | `tests/migrations/` | `migration` | Upgrade/downgrade/data-transform behavior | Required for persistence/migration changes |
| Debug | `tests/debug/` | `debug` | Temporary reproduction/diagnostics only | Excluded from release |

`tests/conftest.py` is the only path-based marker-assignment hook. Purpose buckets listed above receive their dedicated marker. Other first-level domain directories such as `tests/welcome/`, `tests/kubernetes/`, and `tests/storage/` are functional behavior by default.

A fixed defect must finish with the smallest durable regression evidence that proves the behavior. Static/string contracts may supplement business or security behavior but must not be the only proof when executable behavior can be tested.

A page may record Unit or Integration as `N/A` only when the product/architecture contract genuinely has no isolated domain calculation or external/component boundary. The reason must be written in the final-recheck record; `N/A` is not a way to skip difficult tests.

End-to-End Smoke must be deterministic by default: exercise real Flask routing/session/template/application-shell composition, but do not require a developer workstation to run PostgreSQL, Redis, S3, Kubernetes, Prometheus, or Alertmanager unless that smoke test explicitly provisions the dependency. Infrastructure semantics belong in the Integration layer.

Final-reviewed domains have permanent coverage requirements in `scripts/verify_feature_test_coverage.py`. The broad release test command runs all permanent non-E2E evidence, then E2E smoke is invoked explicitly:

```bash
pytest -q -m 'not debug and not e2e'
pytest -q tests/e2e -m e2e
```

Primary targeted commands:

```bash
pytest -q tests/unit -m unit
pytest -q tests/welcome -m functional
pytest -q tests/kubernetes/dashboard -m functional
pytest -q tests/integration -m integration
pytest -q tests/security -m security
pytest -q tests/rendering -m rendering
pytest -q tests/e2e -m e2e
pytest -q tests/contracts -m contract
pytest -q tests/migrations -m migration
```

Do not keep a debug reproduction after its permanent regression test exists.
Inventory final-recheck commands:

```bash
pytest -q tests/unit/kubernetes/inventory -m unit
pytest -q tests/kubernetes/inventory -m functional
pytest -q tests/integration/kubernetes/inventory -m integration
pytest -q tests/security/kubernetes/inventory -m security
pytest -q tests/rendering/kubernetes/inventory -m rendering
pytest -q tests/e2e/kubernetes/inventory -m e2e
pytest -q tests/contracts/kubernetes/test_inventory_final_release_contract.py -m contract
```

The Inventory integration read-model test validates current-generation filtering and SQL pagination through the actual SQLAlchemy repository path. Provider/infrastructure integration remains separate from deterministic application-shell E2E smoke.


- Kubernetes Governance final recheck: `verify_governance_final_lock.py` plus Unit, Functional, Integration, Security, Rendering/UI, E2E, and Governance Contract evidence are mandatory after the domain is reviewed.

## Kubernetes Operations final recheck

```bash
pytest -q tests/unit/kubernetes/operations -m unit
pytest -q tests/kubernetes/operations -m functional
pytest -q tests/integration/kubernetes/operations -m integration
pytest -q tests/security/kubernetes/operations -m security
pytest -q tests/rendering/kubernetes/operations -m rendering
pytest -q tests/e2e/kubernetes/operations -m e2e
pytest -q tests/contracts/kubernetes/operations -m contract
```

Kubernetes Operations E2E smoke exercises real Flask routing/session/application-shell rendering with Kubernetes infrastructure isolated. Live-provider semantics are covered in Integration and domain Functional tests. The final-lock security contract requires RBAC to execute before the cluster prerequisite on every ConfigMap, Secret, Protected Reveal, and TLS operation route.



### Kubernetes Analytics final-recheck evidence

```bash
pytest -q tests/unit/kubernetes/analytics -m unit
pytest -q tests/kubernetes/analytics -m functional
pytest -q tests/integration/kubernetes/analytics -m integration
pytest -q tests/security/kubernetes/analytics -m security
pytest -q tests/rendering/kubernetes/analytics -m rendering
pytest -q tests/e2e/kubernetes/analytics -m e2e
pytest -q tests/contracts/analytics -m contract
```

Analytics uses the same release taxonomy as the previously reviewed domains. The canonical modules are registered in `scripts/verify_feature_test_coverage.py`; additional Analytics domain tests remain valid supporting evidence. Integration owns materialized snapshot persistence/read-model collaboration, while E2E uses the real Flask/session/template shell with external monitoring infrastructure isolated.
