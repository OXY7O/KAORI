# Functional Capability Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a fail-closed functional capability inventory for every active KAORI release surface, mapped to existing executable evidence without adding a new runner or changing product behavior.

**Architecture:** Add one reviewed JSON matrix under `docs/architecture/` and one release contract under `tests/contracts/release/`. The contract derives the canonical surface set from `scripts/release_surface_registry.py`, validates matrix structure/evidence/dispositions, and fails closed on registry drift. The matrix references existing Full Admission authorities and records explicit `covered`, `bounded_gap`, or `not_applicable` state per behavior dimension.

**Tech Stack:** Python 3, pytest contract tests, JSON, existing KAORI release registry and quality-gate infrastructure.

**Spec:** `docs/superpowers/specs/2026-09-13-functional-capability-audit-design.md`

## Global Constraints

- Base authority: `kaori/staging@6847255790cb184f3b3beaeeaee80e2173d43f9c`.
- Parent issue: #225; milestone: UI & Functional Quality (#3).
- Initial implementation changes governance/test artifacts only; no production application, migration, schema, runtime, or CI workflow behavior changes.
- Do not introduce a custom verifier script or a second test runner.
- `scripts/release_surface_registry.py` remains the canonical shipping-surface authority.
- Existing Full Admission functional/domain/E2E/static authorities remain execution authority.
- Kubernetes Tenant Management (#61, #112–#125) remains excluded.
- Runtime/degraded UX remains coordinated with #228; navigation with #226; accessibility with #227; responsive/device behavior with #224.
- `main`, RC/tag, staging-server deployment, and human UAT are out of scope for this increment.
- Use TDD: release contract RED first, then minimum matrix GREEN.

---

## File Structure

- Create `tests/contracts/release/test_functional_capability_audit_contract.py` — fail-closed schema/registry/evidence contract.
- Create `docs/architecture/functional-capability-audit-matrix.json` — reviewed inventory and evidence/disposition map.
- Modify `docs/superpowers/plans/2026-09-13-functional-capability-audit-implementation-plan.md` only if implementation discovers a contradiction in this plan; do not silently change scope.
- No production file is modified in this initial inventory increment.

The contract and matrix intentionally live separately: the JSON is human-reviewable audit state, while pytest remains the existing release-governance execution mechanism.

---

### Task 1: Establish the Fail-Closed Contract in RED

**Files:**
- Create: `tests/contracts/release/test_functional_capability_audit_contract.py`
- Read: `scripts/release_surface_registry.py`
- Read: `docs/architecture/ui-standard-audit-matrix.json`

**Interfaces:**
- Consumes: `scripts/release_surface_registry.py::SURFACES` and each `ReleaseSurface` field.
- Produces: constants `MATRIX_PATH`, `CANONICAL_BEHAVIOR_DIMENSIONS`, `VALID_BEHAVIOR_STATES`, helper `_assert_paths_exist(paths: list[str], *, context: str) -> None`, and the release contract consumed by Task 2.

- [ ] **Step 1: Write the failing release contract**

Create the test module with the following contract shape:

```python
from __future__ import annotations

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'functional-capability-audit-matrix.json'

CANONICAL_BEHAVIOR_DIMENSIONS = {
    'normal_flow',
    'authorization',
    'validation_dependency',
    'persistence',
    'async_job',
    'export_publication',
    'failure_recovery',
}
VALID_BEHAVIOR_STATES = {'covered', 'bounded_gap', 'not_applicable'}
REQUIRED_EXECUTION_AUTHORITIES = {
    'scripts/quality_gate.sh',
    'scripts/verify_feature_test_coverage.py',
    'scripts/verify_test_domain_architecture.py',
    'tests/contracts',
    'tests/e2e',
}


def _assert_paths_exist(paths: list[str], *, context: str) -> None:
    assert paths, f'{context}: evidence paths must not be empty'
    missing = [path for path in paths if not (ROOT / path).exists()]
    assert not missing, f'{context}: missing evidence paths: {missing}'


def test_functional_capability_audit_matrix_is_fail_closed() -> None:
    assert MATRIX_PATH.exists(), (
        'Functional capability audit matrix is missing; #225 requires every active release surface '
        'and capability behavior to have executable evidence or explicit disposition.'
    )

    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    assert payload['version'] == 1
    assert payload['phase'] == 'inventory'
    assert payload['source_registry'] == 'scripts/release_surface_registry.py'
    assert set(payload['execution_authorities']) == REQUIRED_EXECUTION_AUTHORITIES
    _assert_paths_exist(payload['execution_authorities'], context='execution authorities')
    assert set(payload['behavior_dimensions']) == CANONICAL_BEHAVIOR_DIMENSIONS

    registry = runpy.run_path(str(ROOT / 'scripts' / 'release_surface_registry.py'))
    surfaces = {surface.key: surface for surface in registry['SURFACES']}
    matrix = payload['surfaces']
    assert set(matrix) == set(surfaces), (
        f'functional audit coverage must exactly match release authority; '
        f'missing={sorted(set(surfaces) - set(matrix))}, extra={sorted(set(matrix) - set(surfaces))}'
    )

    for key, surface in surfaces.items():
        entry = matrix[key]
        expected_classification = 'system_non_ui' if key == 'health' else 'active_ui'
        assert entry['classification'] == expected_classification
        assert entry['title'] == surface.title
        assert entry['entrypoints'] == list(surface.navigation_endpoints)

        release_evidence = entry['release_evidence']
        assert set(surface.verifiers).issubset(release_evidence['verifiers'])
        assert set(surface.contract_paths).issubset(release_evidence['contracts'])
        if release_evidence['verifiers']:
            _assert_paths_exist(release_evidence['verifiers'], context=f'{key} release verifiers')
        _assert_paths_exist(release_evidence['contracts'], context=f'{key} release contracts')

        capabilities = entry['capabilities']
        assert capabilities, f'{key}: at least one capability is required'
        for capability_key, capability in capabilities.items():
            assert capability['state'] == 'active', f'{key}.{capability_key}: capability must be active'
            behaviors = capability['behaviors']
            assert behaviors, f'{key}.{capability_key}: at least one behavior is required'
            assert set(behaviors).issubset(CANONICAL_BEHAVIOR_DIMENSIONS)

            for behavior_key, behavior in behaviors.items():
                assert behavior['state'] in VALID_BEHAVIOR_STATES
                state = behavior['state']
                if state == 'covered':
                    evidence = behavior['evidence']
                    _assert_paths_exist(evidence, context=f'{key}.{capability_key}.{behavior_key}')
                    assert not any(path.startswith('tests/debug') for path in evidence)
                    assert 'reason' not in behavior
                    assert 'tracking_issue' not in behavior
                elif state == 'bounded_gap':
                    assert behavior['reason'].strip()
                    assert isinstance(behavior['tracking_issue'], int) and behavior['tracking_issue'] > 0
                    assert not behavior.get('evidence')
                else:
                    assert behavior['reason'].strip()
                    assert not behavior.get('evidence')
                    assert 'tracking_issue' not in behavior
```

The first RED is intentionally the missing matrix assertion. Do not create the matrix in the same commit.

- [ ] **Step 2: Commit the RED test only**

```bash
git add tests/contracts/release/test_functional_capability_audit_contract.py
git commit -m "test(release): define functional capability audit contract (#225)"
```

- [ ] **Step 3: Run Developer Check and verify valid RED**

Expected path-aware Developer Check result:

```text
FAIL tests/contracts/release/test_functional_capability_audit_contract.py::test_functional_capability_audit_matrix_is_fail_closed
AssertionError: Functional capability audit matrix is missing
```

All prerequisite formatting/static/type gates routed by the Developer Check must pass before treating the failure as authoritative RED. Record run number, exact SHA, failing test count, and artifact hash in #225/PR #366.

---

### Task 2: Add the Minimum Inventory Matrix in GREEN

**Files:**
- Create: `docs/architecture/functional-capability-audit-matrix.json`
- Test: `tests/contracts/release/test_functional_capability_audit_contract.py`
- Read: `scripts/release_surface_registry.py`
- Read: existing test paths referenced below before marking a behavior `covered`.

**Interfaces:**
- Consumes: the Task 1 schema exactly.
- Produces: schema version `1`, phase `inventory`, exact release-surface key coverage, capability behavior evidence/dispositions.

- [ ] **Step 1: Create the top-level matrix structure**

Use exactly these top-level fields:

```json
{
  "version": 1,
  "phase": "inventory",
  "source_registry": "scripts/release_surface_registry.py",
  "execution_authorities": [
    "scripts/quality_gate.sh",
    "scripts/verify_feature_test_coverage.py",
    "scripts/verify_test_domain_architecture.py",
    "tests/contracts",
    "tests/e2e"
  ],
  "behavior_dimensions": [
    "normal_flow",
    "authorization",
    "validation_dependency",
    "persistence",
    "async_job",
    "export_publication",
    "failure_recovery"
  ],
  "surfaces": {}
}
```

- [ ] **Step 2: Populate every release surface with exact registry ownership**

The matrix must contain exactly these surface keys from `SURFACES`:

```text
welcome
dashboard
inventory
object_storage_inventory
kubernetes_operations
governance
analytics
intelligence
reports
integrations
platform_operations
access
settings
authentication
notifications
health
```

For each surface:

- `title` equals the registry title.
- `classification` is `active_ui`, except `health` = `system_non_ui`.
- `entrypoints` equals `list(surface.navigation_endpoints)` exactly.
- `release_evidence.verifiers` includes every registry verifier.
- `release_evidence.contracts` includes every registry contract path.

Do not copy release evidence from another surface to make the contract pass.

- [ ] **Step 3: Populate capability groups using this exact inventory boundary**

Use these capability keys under their owning surfaces:

| Surface | Capability keys |
| --- | --- |
| `welcome` | `workspace_entry` |
| `dashboard` | `kubernetes_dashboard`, `object_storage_dashboard` |
| `inventory` | `overview`, `nodes`, `namespaces`, `workloads`, `pods`, `services`, `ingresses`, `storage`, `configuration`, `topology` |
| `object_storage_inventory` | `overview`, `systems`, `buckets` |
| `kubernetes_operations` | `configmap_management`, `secret_management` |
| `governance` | `tls_certificates` |
| `analytics` | `kubernetes_overview`, `utilization`, `capacity`, `storage`, `workload`, `forecast`, `top_consumers`, `alerts`, `object_storage_overview`, `object_storage_capacity`, `object_storage_performance`, `object_storage_forecast`, `object_storage_top_consumers`, `object_storage_alerts` |
| `intelligence` | `recommendations`, `alert_intelligence`, `rule_catalog`, `automation_control` |
| `reports` | `overview`, `generate`, `generated`, `templates`, `schedules`, `storage`, `pdf_publication`, `xlsx_publication`, `csv_publication` |
| `integrations` | `overview`, `kubernetes_provider`, `prometheus_provider`, `alertmanager_provider`, `object_storage_provider`, `notification_channels` |
| `platform_operations` | `overview`, `job_executions`, `data_lifecycle`, `kubernetes_operations_center` |
| `access` | `overview`, `users`, `identity_providers`, `roles`, `permissions`, `activity_audit` |
| `settings` | `general`, `account` |
| `authentication` | `login`, `logout`, `session`, `readiness` |
| `notifications` | `notification_center`, `inbox`, `activity`, `read_state_refresh` |
| `health` | `liveness`, `readiness` |

Each capability must use:

```json
{
  "state": "active",
  "behaviors": {
    "normal_flow": {
      "state": "covered",
      "evidence": ["tests/.../test_....py"]
    }
  }
}
```

Do not add dimensions that do not semantically apply merely to make the matrix look complete.

- [ ] **Step 4: Map evidence conservatively**

Before marking a behavior `covered`, open the referenced test/verifier and confirm it exercises that declared behavior. Prefer the narrowest existing executable authority in this order:

1. behavior-specific functional/domain characterization test;
2. integration or security test for persistence/authorization/dependency boundaries;
3. contract/verifier for static publication/architecture invariants;
4. E2E/browser evidence for representative user-visible reachability.

Examples of valid mappings already known from current release governance:

```json
{
  "authentication": {
    "login": {
      "state": "active",
      "behaviors": {
        "normal_flow": {
          "state": "covered",
          "evidence": ["tests/access/authentication/test_login_characterization.py"]
        },
        "authorization": {
          "state": "covered",
          "evidence": ["tests/security/access/authentication/test_authentication_security.py"]
        },
        "failure_recovery": {
          "state": "covered",
          "evidence": ["tests/ui/test_runtime_state_responsiveness.py"]
        }
      }
    }
  }
}
```

```json
{
  "reports": {
    "pdf_publication": {
      "state": "active",
      "behaviors": {
        "export_publication": {
          "state": "covered",
          "evidence": [
            "scripts/verify_report_generation_contract.py",
            "tests/contracts/reports"
          ]
        }
      }
    }
  }
}
```

If no relevant evidence can be confirmed during inventory, use:

```json
{
  "state": "bounded_gap",
  "reason": "No existing release evidence directly exercises the declared capability behavior; audit decomposition required.",
  "tracking_issue": 225
}
```

Do not manufacture a product test or production change inside this task to avoid a `bounded_gap`.

For a genuinely non-applicable behavior, use:

```json
{
  "state": "not_applicable",
  "reason": "This read-only capability does not mutate durable state."
}
```

- [ ] **Step 5: Run the focused contract**

Run:

```bash
pytest -q tests/contracts/release/test_functional_capability_audit_contract.py
```

Expected: PASS.

If it fails because an evidence path does not exist, correct the mapping; do not weaken `_assert_paths_exist`.

- [ ] **Step 6: Commit the GREEN inventory**

```bash
git add docs/architecture/functional-capability-audit-matrix.json
git commit -m "docs(audit): inventory functional capabilities and evidence (#225)"
```

- [ ] **Step 7: Run exact-head Developer Check**

Developer Check must include the new release contract through the validation-authority route. Expected: all routed static/contract checks PASS. Record exact head SHA, run number, counts, and artifact hash in #225 and PR #366.

---

### Task 3: Review the Inventory for Genuine Findings Without Expanding Scope

**Files:**
- Modify only if review finds incorrect audit state: `docs/architecture/functional-capability-audit-matrix.json`
- Do not modify production code in this task.

**Interfaces:**
- Consumes: Task 2 GREEN matrix.
- Produces: a reviewed set of `bounded_gap` findings with truthful reasons and ownership; no silent gaps.

- [ ] **Step 1: Enumerate every `bounded_gap` entry**

Review the JSON and build an issue comment table with columns:

```text
Surface | Capability | Behavior | Reason | Tracking owner | Severity/disposition
```

Every `bounded_gap` must remain visible in this table.

- [ ] **Step 2: Classify each gap using the spec rules**

Use exactly these dispositions:

- `functional_defect_high` — dedicated linked child issue required before milestone completion.
- `functional_defect_medium_low` — bounded child issue unless trivial and reviewable within #225.
- `evidence_only_gap` — behavior appears correct; add focused regression in a separate TDD increment.
- `runtime_error_state` — link to #228 and retain capability mapping in #225.
- `intentional_deferred` — only when a durable existing issue/roadmap authority proves the behavior is intentionally inactive/deferred.

Do not close a gap by changing its state to `covered` without executable evidence.

- [ ] **Step 3: Correct matrix mistakes only**

If review reveals a mapping error, update only the affected JSON entry, rerun:

```bash
pytest -q tests/contracts/release/test_functional_capability_audit_contract.py
```

Expected: PASS.

Commit mapping corrections separately:

```bash
git add docs/architecture/functional-capability-audit-matrix.json
git commit -m "docs(audit): correct functional capability evidence mapping (#225)"
```

Skip this commit if no mapping correction is required.

- [ ] **Step 4: Publish the inventory checkpoint**

Add a #225 comment that records:

- exact work-head SHA;
- Developer Check run and result;
- number of surfaces;
- number of capabilities;
- count of `covered`, `bounded_gap`, and `not_applicable` behaviors;
- linked child findings created or delegated to #228;
- explicit statement that no production behavior was changed in this initial inventory increment.

Update PR #366 body with the same implementation evidence, but do not mark Ready until all required Developer Check/review gates are complete.

---

### Task 4: Freeze the Initial Inventory Candidate and Admit It to Staging

**Files:**
- No source change expected after candidate freeze.

**Interfaces:**
- Consumes: reviewed Task 3 work head.
- Produces: admitted staging inventory authority for subsequent #225 child audit increments and #228 consumption.

- [ ] **Step 1: Perform Pre-Ready checks**

Verify:

```text
PR #366 is Draft
exact head Developer Check = PASS
base = kaori/staging
base SHA has not drifted unexpectedly
review submissions = 0 blocking
unresolved review threads = 0
changed files are limited to approved #225 design/plan/contract/matrix artifacts
```

If staging moved, compare before updating the branch; never overwrite unrelated admitted work.

- [ ] **Step 2: Mark PR #366 Ready**

Wait for any Ready-triggered Developer Check on the exact same head to reach terminal PASS.

- [ ] **Step 3: Merge with expected-head guard**

Use regular merge to `kaori/staging` with the exact final PR head SHA.

- [ ] **Step 4: Require fresh Full Admission**

On the exact merged staging SHA, require terminal PASS for:

```text
Resolve Profile
Static & Governance
Security
Functional Tests
Frontend
Runtime & DAST
CI Admission
```

Capture exact functional counts, runtime/DAST results, and immutable Full Admission artifact digest.

- [ ] **Step 5: Record staging admission and keep #225 open**

Add a #225 checkpoint stating that the **inventory authority is admitted**, while #225 remains open for capability-by-capability audit and bounded child findings. Do not claim milestone human UAT or close #225 merely because the inventory matrix is admitted.

---

## Plan Self-Review

- Spec coverage: initial fail-closed matrix, release-registry alignment, canonical behavior states, existing evidence reuse, bounded gaps, #228 delegation, TDD, GitHub staging flow, and completion boundary are represented.
- Scope: this plan deliberately covers the first independently reviewable #225 inventory increment; product defect repairs are separate child increments after the matrix exposes them.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Interface consistency: Task 2 uses the exact schema/constants defined by Task 1; Tasks 3–4 consume the same matrix without adding a second authority.
