from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
SECRET_ROOT = ROOT / 'app/kubernetes_operations/secrets'


def _module(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load(name: str, path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


class Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters: list[dict[str, object]] = []

    def filter_by(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def yield_per(self, count):
        return iter(self.rows)


def load_impact(
    monkeypatch: pytest.MonkeyPatch,
    *,
    evidence_state: str,
    pods: list[object],
):
    for name in (
        'app',
        'app.common',
        'app.common.inventory_generation',
        'app.inventory',
        'app.inventory.resources',
        'app.inventory.resources.configuration_semantics',
        'app.inventory.resources.pod_semantics',
        'app.kubernetes_operations',
        'app.kubernetes_operations.secrets',
        'app.kubernetes_operations.secrets.live_service',
        'app.models',
    ):
        _module(name, monkeypatch)

    contracts = _load(
        'app.kubernetes_operations.secrets.contracts',
        SECRET_ROOT / 'contracts.py',
        monkeypatch,
    )
    current_generation_calls: list[object] = []
    sys.modules['app.common.inventory_generation'].filter_current_generation = lambda query, model: (
        current_generation_calls.append(model) or query
    )
    semantics = sys.modules['app.inventory.resources.configuration_semantics']
    semantics.COLLECTED = 'Collected'
    semantics.POD_EVIDENCE_KEY = 'inventory.pods'
    semantics.collection_state = lambda evidence, key: evidence.get(key, 'Not Reported')
    sys.modules['app.inventory.resources.pod_semantics'].pod_operational_state = lambda phase, ready: (
        'Stable',
        'normal',
        f'{phase} · {ready}',
    )
    sys.modules['app.kubernetes_operations.secrets.live_service'].LiveSecretSnapshot = type(
        'LiveSecretSnapshot',
        (),
        {},
    )

    cluster_query = Query([SimpleNamespace(collection_evidence={'inventory.pods': evidence_state})])
    pod_query = Query(pods)
    models = sys.modules['app.models']
    models.ClusterInventory = type('ClusterInventory', (), {'query': cluster_query})
    models.PodInventory = type('PodInventory', (), {'query': pod_query})

    impact = _load('secret_impact_under_test', SECRET_ROOT / 'impact.py', monkeypatch)
    return impact, contracts, current_generation_calls, pod_query


def target():
    return SimpleNamespace(
        cluster=SimpleNamespace(id=7),
        namespace='default',
        name='application-secret',
    )


def test_missing_pod_collection_is_not_reported_instead_of_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    impact, _, calls, pod_query = load_impact(
        monkeypatch,
        evidence_state='Permission Unavailable',
        pods=[],
    )

    result = impact.get_secret_impact_context(target())

    assert result.reported is False
    assert result.count is None
    assert result.display == 'Not Reported'
    assert calls == []
    assert pod_query.filters == []


def test_collected_pod_evidence_uses_current_generation_and_deduplicates_workloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    references = [{'type': 'Secret', 'name': 'application-secret'}]
    pods = [
        SimpleNamespace(
            configuration_references=references,
            workload_type='Deployment',
            workload_name='api',
            pod_name='api-a',
            phase='Running',
            ready='1/1',
        ),
        SimpleNamespace(
            configuration_references=references,
            workload_type='Deployment',
            workload_name='api',
            pod_name='api-b',
            phase='Running',
            ready='1/1',
        ),
    ]
    impact, _, calls, pod_query = load_impact(
        monkeypatch,
        evidence_state='Collected',
        pods=pods,
    )

    result = impact.get_secret_impact_context(target())

    assert result.reported is True
    assert result.count == 1
    assert result.display == '1 Workload Reference'
    assert result.items[0]['name'] == 'api'
    assert len(calls) == 1
    assert pod_query.filters == [{'cluster_id': 7, 'namespace': 'default'}]
