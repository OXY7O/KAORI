from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load_repository(filter_current_generation, monkeypatch: pytest.MonkeyPatch):
    for package in ('app', 'app.common', 'app.extensions', 'app.dashboards', 'app.kubernetes.dashboard'):
        module = ModuleType(package)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, package, module)

    generation = ModuleType('app.common.inventory_generation')
    generation.filter_current_generation = filter_current_generation
    monkeypatch.setitem(sys.modules, 'app.common.inventory_generation', generation)

    raw_query = SimpleNamespace(name='raw-query')
    db_module = ModuleType('app.extensions.db')
    db_module.db = SimpleNamespace(session=SimpleNamespace(query=lambda model: raw_query))
    monkeypatch.setitem(sys.modules, 'app.extensions.db', db_module)

    name = 'app.kubernetes.dashboard.repository'
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / 'app/kubernetes/dashboard/repository.py',
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module, raw_query


def test_dashboard_repository_applies_committed_generation_to_inventory_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, object]] = []
    committed_query = SimpleNamespace(name='committed-query')

    def committed(query, model):
        calls.append((query, model))
        return committed_query

    repository, raw_query = _load_repository(committed, monkeypatch)

    class InventoryModel:
        cluster_id = object()
        collected_at = object()

    assert repository._query(InventoryModel) is committed_query
    assert calls == [(raw_query, InventoryModel)]


def test_dashboard_repository_does_not_apply_inventory_generation_to_platform_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, object]] = []

    def committed(query, model):
        calls.append((query, model))
        return query

    repository, raw_query = _load_repository(committed, monkeypatch)

    class PlatformModel:
        created_at = object()

    assert repository._query(PlatformModel) is raw_query
    assert calls == []
