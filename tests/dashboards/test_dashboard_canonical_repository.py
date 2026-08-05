from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def _load_repository(filter_current_generation):
    for package in ('app', 'app.common', 'app.extensions', 'app.dashboards', 'app.dashboards.kubernetes'):
        module = sys.modules.setdefault(package, ModuleType(package))
        module.__path__ = []

    generation = ModuleType('app.common.inventory_generation')
    generation.filter_current_generation = filter_current_generation
    sys.modules['app.common.inventory_generation'] = generation

    raw_query = SimpleNamespace(name='raw-query')
    db_module = ModuleType('app.extensions.db')
    db_module.db = SimpleNamespace(session=SimpleNamespace(query=lambda model: raw_query))
    sys.modules['app.extensions.db'] = db_module

    name = 'app.dashboards.kubernetes.repository'
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / 'app/dashboards/kubernetes/repository.py',
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module, raw_query


def test_dashboard_repository_applies_committed_generation_to_inventory_models() -> None:
    calls: list[tuple[object, object]] = []
    committed_query = SimpleNamespace(name='committed-query')

    def committed(query, model):
        calls.append((query, model))
        return committed_query

    repository, raw_query = _load_repository(committed)

    class InventoryModel:
        cluster_id = object()
        collected_at = object()

    assert repository._query(InventoryModel) is committed_query
    assert calls == [(raw_query, InventoryModel)]


def test_dashboard_repository_does_not_apply_inventory_generation_to_platform_models() -> None:
    calls: list[tuple[object, object]] = []

    def committed(query, model):
        calls.append((query, model))
        return query

    repository, raw_query = _load_repository(committed)

    class PlatformModel:
        created_at = object()

    assert repository._query(PlatformModel) is raw_query
    assert calls == []
