"""Regression evidence for capability-aware Developer Check selection and release ownership."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from developer_check_plan import build_plan  # noqa: E402
from release_surface_registry import SURFACES  # noqa: E402
from verify_release_surface_coverage import ROOT, _contract_test_modules  # noqa: E402


def test_artifact_registry_changes_select_their_own_contracts() -> None:
    plan = build_plan(['app/artifact_registry/analytics.py'])

    assert plan.python and plan.contracts
    assert 'artifact_registry' in plan.capabilities
    assert 'tests/contracts/artifact_registry' in plan.normalized_test_paths()
    assert 'tests/contracts/release' not in plan.normalized_test_paths()


def test_registry_source_and_unit_contract_edits_route_owning_tests() -> None:
    for changed_path in (
        'app/artifact_registry/presentation_inventory.py',
        'tests/unit/artifact_registry/test_registry_inventory_bounded_detail.py',
    ):
        plan = build_plan([changed_path])
        assert plan.python
        assert 'artifact_registry' in plan.capabilities
        assert 'tests/unit/artifact_registry' in plan.normalized_test_paths()


def test_artifact_registry_contract_changes_remain_routed() -> None:
    plan = build_plan(['tests/contracts/artifact_registry/test_example_contract.py'])

    assert plan.contracts
    assert 'tests/contracts/artifact_registry' in plan.normalized_test_paths()


def test_registry_provider_changes_select_registry_consumer_contracts() -> None:
    plan = build_plan(['app/integrations/registry/providers/harbor/client.py'])

    assert {'integrations', 'artifact_registry'} <= plan.capabilities
    assert 'tests/contracts/artifact_registry' in plan.normalized_test_paths()
    assert 'tests/unit/artifact_registry' in plan.normalized_test_paths()


def test_object_storage_changes_select_own_contracts() -> None:
    plan = build_plan(['app/storage/object_storage/analytics/service.py'])

    assert plan.python and plan.contracts
    assert 'storage/object_storage' in plan.capabilities
    assert 'tests/contracts/storage/object_storage' in plan.normalized_test_paths()
    assert 'tests/contracts/release' not in plan.normalized_test_paths()


def test_object_storage_provider_changes_select_storage_consumer_contracts() -> None:
    plan = build_plan(['app/integrations/storage/object_storage/providers/minio/client.py'])

    assert {'integrations', 'storage/object_storage'} <= plan.capabilities
    assert 'tests/contracts/storage/object_storage' in plan.normalized_test_paths()


def test_registry_workspace_template_selects_registry_contracts() -> None:
    plan = build_plan(['app/templates/artifact_registry/inventory.html'])

    assert plan.templates and plan.contracts
    assert 'artifact_registry' in plan.capabilities
    assert 'tests/contracts/artifact_registry' in plan.normalized_test_paths()


def test_object_storage_frontend_asset_selects_storage_contracts() -> None:
    plan = build_plan(['app/static/js/storage/object_storage/analytics.js'])

    assert plan.frontend and plan.contracts
    assert 'storage/object_storage' in plan.capabilities
    assert 'tests/contracts/storage/object_storage' in plan.normalized_test_paths()


def test_unrelated_access_change_does_not_select_storage_or_registry() -> None:
    plan = build_plan(['app/access/users/service.py'])

    assert 'access' in plan.capabilities
    assert 'artifact_registry' not in plan.capabilities
    assert 'storage/object_storage' not in plan.capabilities
    assert 'tests/contracts/artifact_registry' not in plan.normalized_test_paths()
    assert 'tests/contracts/storage/object_storage' not in plan.normalized_test_paths()


def test_shared_quality_authority_still_widens_contract_coverage() -> None:
    plan = build_plan(['scripts/quality_gate.sh'])

    assert plan.wide and plan.contracts and plan.migrations
    assert 'tests/contracts' in plan.normalized_test_paths()
    assert 'tests/migrations' in plan.normalized_test_paths()


def test_release_evidence_directory_requires_real_test_modules(tmp_path: Path) -> None:
    empty = tmp_path / 'contracts'
    empty.mkdir()
    (empty / '__init__.py').write_text('', encoding='utf-8')
    assert _contract_test_modules(empty) == []

    nested = empty / 'registry'
    nested.mkdir()
    module = nested / 'test_provider_scope.py'
    module.write_text('def test_scope(): pass\n', encoding='utf-8')
    assert _contract_test_modules(empty) == [module]


def test_release_evidence_file_must_be_a_test_module(tmp_path: Path) -> None:
    helper = tmp_path / 'helpers.py'
    helper.write_text('pass\n', encoding='utf-8')
    assert _contract_test_modules(helper) == []

    test_module = tmp_path / 'test_contract.py'
    test_module.write_text('def test_contract(): pass\n', encoding='utf-8')
    assert _contract_test_modules(test_module) == [test_module]


def test_release_surface_coverage_output_distinguishes_registration_from_execution() -> None:
    """Registered contracts and optional verifiers must not imply a domain test PASS."""
    quality_gate = (ROOT / 'scripts/quality_gate.sh').read_text(encoding='utf-8')
    assert "'Release Surface Coverage' 'python scripts/verify_release_surface_coverage.py'" in quality_gate
    assert quality_gate.count("'Release Surface Coverage' 'python scripts/verify_release_surface_coverage.py'") == 1
    assert 'RELEASE_SURFACE_COVERAGE_LOG="$log_file"' in quality_gate
    assert 'if [[ "$group" == \'Domain & Capability Contracts\' ]]' in quality_gate
    assert 'Registered capability ownership' in quality_gate
    assert 'Source ownership only — NOT executed tests or Staging Acceptance.' in quality_gate
    assert '            /^  REGISTERED — / {' in quality_gate
    assert 'FAIL — malformed or empty registered capability ownership' in quality_gate
    assert 'Full verifier mapping: %s' in quality_gate

    source = (ROOT / 'scripts/verify_release_surface_coverage.py').read_text(encoding='utf-8')
    assert 'EVIDENCE REGISTERED ONLY' in source
    assert 'REGISTERED — {surface.title}' in source
    assert 'none (contract tests only)' in source
    assert 'surface.lock_state' in source

    surfaces = {surface.key: surface for surface in SURFACES}
    assert surfaces['artifact_registry'].contract_paths
    assert surfaces['artifact_registry'].verifiers == ()
    assert surfaces['tenant'].contract_paths
    assert surfaces['tenant'].verifiers == ()
    assert surfaces['object_storage_inventory'].verifiers
    assert surfaces['analytics'].verifiers
    assert surfaces['integrations'].verifiers
