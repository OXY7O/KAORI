from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, relative_path: str) -> ModuleType:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_internal_import_modules_and_symbols_are_resolvable() -> None:
    verifier = _load(
        'kaori_internal_import_symbols',
        'scripts/verify_internal_import_symbols.py',
    )
    assert verifier.validate(ROOT) == []


def test_runtime_import_graph_is_acyclic() -> None:
    verifier = _load('kaori_runtime_import_cycles', 'scripts/verify_import_cycles.py')
    modules = verifier._discover_modules()
    graph = verifier._build_graph(modules)
    assert verifier._strongly_connected_components(graph) == []


def test_module_reachability_gate_has_no_orphan_application_modules() -> None:
    verifier = _load('kaori_module_reachability', 'scripts/verify_module_reachability.py')
    assert verifier.validate(ROOT) == []


def test_test_taxonomy_uses_one_canonical_location_marker_hook() -> None:
    verifier = _load('kaori_test_taxonomy', 'scripts/verify_test_taxonomy.py')
    assert verifier.validate(ROOT) == []


def test_feature_characterization_evidence_is_present() -> None:
    verifier = _load(
        'kaori_feature_test_coverage',
        'scripts/verify_feature_test_coverage.py',
    )
    assert verifier.validate(ROOT) == []


def test_ui_reuse_debt_cannot_expand() -> None:
    verifier = _load('kaori_ui_reuse', 'scripts/verify_ui_reuse.py')
    baseline = ROOT / 'docs/architecture/ui-inline-debt-baseline.json'
    assert verifier.validate(ROOT, baseline) == []


def test_dormant_large_query_foundation_is_retired_until_a_worker_uses_it() -> None:
    for relative_path in (
        'app/jobs/query_execution.py',
        'app/jobs/query_planning.py',
        'app/jobs/resource_limits.py',
    ):
        assert not (ROOT / relative_path).exists()

    architecture_gate = (ROOT / 'scripts/verify_architecture_boundaries.py').read_text(
        encoding='utf-8'
    )
    for module in (
        'app.jobs.query_execution',
        'app.jobs.query_planning',
        'app.jobs.resource_limits',
    ):
        assert module in architecture_gate


def test_source_hygiene_scans_archives_without_git_metadata() -> None:
    source = (ROOT / 'scripts/verify_source_hygiene.sh').read_text(encoding='utf-8')
    assert "source_label='source archive'" in source
    assert 'find .' in source
    assert 'tracked-file validation was skipped' not in source


def test_release_gate_runs_format_type_taxonomy_and_ui_checks() -> None:
    source = (ROOT / 'scripts/quality_gate.sh').read_text(encoding='utf-8')
    for command in (
        'verify_python_syntax.py',
        'ruff check',
        'ruff format --check',
        'djlint app/templates --check',
        'pyright --project pyrightconfig.json',
        'verify_internal_import_symbols.py',
        'verify_import_cycles.py',
        'verify_module_reachability.py',
        'verify_test_taxonomy.py',
        'verify_feature_test_coverage.py',
        'verify_ui_reuse.py',
        'npm run check-format',
        'pytest -q tests/analytics tests/inventory tests/kubernetes -m functional',
    ):
        assert command in source
