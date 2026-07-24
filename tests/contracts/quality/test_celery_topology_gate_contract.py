from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[3]


def _load_verifier():
    path = ROOT / 'scripts' / 'verify_celery_topology.py'
    spec = importlib.util.spec_from_file_location('kaori_celery_topology_verifier', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_celery_topology_is_closed_in_production() -> None:
    verifier = _load_verifier()
    assert verifier.validate(ROOT) == []


def test_topology_verifier_checks_routes_workers_and_job_execution_contract() -> None:
    source = (ROOT / 'scripts' / 'verify_celery_topology.py').read_text(encoding='utf-8')
    assert 'Celery task has no explicit route' in source
    assert 'Celery routed queue has no production worker' in source
    assert 'Production worker consumes a queue with no registered task route' in source
    assert 'job_execution_id' in source
