from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]


def _load_verifier():
    path = ROOT / 'scripts/verify_architecture_boundaries.py'
    spec = importlib.util.spec_from_file_location('kaori_architecture_verifier', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_architecture_boundary_verifier_passes_current_source() -> None:
    verifier = _load_verifier()
    app_root = ROOT / 'app'
    baseline = json.loads(
        (ROOT / 'docs/architecture/architecture-debt-baseline.json').read_text(encoding='utf-8')
    )

    records = verifier.scan_imports(app_root)
    errors = verifier.validate_boundaries(app_root, records, baseline)

    assert errors == []


def test_retired_compatibility_and_empty_artifacts_are_absent() -> None:
    retired = (
        'app/inventory/collector.py',
        'app/inventory/service.py',
        'app/integrations/runtime/contracts.py',
        'app/integrations/prometheus/evidence.py',
        'app/utils/helpers.py',
        'app/static/js/dashboard.js',
        'app/static/js/report.js',
    )

    assert [path for path in retired if (ROOT / path).exists()] == []


def test_kubernetes_inventory_adapter_uses_canonical_use_case() -> None:
    source = (ROOT / 'app/integrations/kubernetes/inventory.py').read_text(encoding='utf-8')

    assert 'from app.inventory.synchronization import sync_inventory' in source
    assert 'app.inventory.service' not in source


def test_runtime_repository_uses_canonical_integration_contract() -> None:
    source = (ROOT / 'app/integrations/runtime/repository.py').read_text(encoding='utf-8')

    assert 'from app.integrations.contracts import RuntimeState' in source
    assert 'from .contracts import RuntimeState' not in source


def test_architecture_verifier_blocks_imports_to_retired_python_modules(tmp_path: Path) -> None:
    verifier = _load_verifier()
    app_root = tmp_path / 'app'
    module = app_root / 'example.py'
    module.parent.mkdir(parents=True)
    module.write_text(
        'from app.integrations.runtime.contracts import RuntimeState\n',
        encoding='utf-8',
    )

    records = verifier.scan_imports(app_root)
    errors = verifier.validate_boundaries(
        app_root,
        records,
        {'cycle_envelopes': [], 'service_form_imports': []},
    )

    assert any('import targets retired module' in error for error in errors)
