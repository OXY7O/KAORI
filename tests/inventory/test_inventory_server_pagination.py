from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.common.pagination import build_pagination_window, pagination_payload
from app.inventory.resources import configuration, ingresses, namespaces, nodes, pods, services, storage, workloads


class _QueryStub:
    def join(self, *_args: Any, **_kwargs: Any) -> _QueryStub:
        return self

    def filter(self, *_args: Any, **_kwargs: Any) -> _QueryStub:
        return self

    def with_entities(self, *_args: Any, **_kwargs: Any) -> _QueryStub:
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> _QueryStub:
        return self

    def all(self) -> list[Any]:
        return []


@pytest.mark.parametrize(
    ('module', 'service_name', 'rows_key'),
    [
        (nodes, 'get_node_inventory', 'nodes'),
        (namespaces, 'get_namespace_inventory', 'namespaces'),
        (configuration, 'get_configuration_inventory_view', 'items'),
        (workloads, 'get_workload_inventory', 'workloads'),
        (pods, 'get_pod_inventory', 'pods'),
        (services, 'get_service_inventory', 'services'),
        (ingresses, 'get_ingress_inventory', 'ingresses'),
        (storage, 'get_storage_inventory_view', 'storage_items'),
    ],
)
def test_resource_services_delegate_page_windows_to_canonical_query_pagination(
    monkeypatch,
    module,
    service_name: str,
    rows_key: str,
) -> None:
    captured: list[tuple[int, int]] = []
    query = _QueryStub()
    monkeypatch.setattr(module.db, 'session', SimpleNamespace(query=lambda *_args: query))

    def paginate(query_arg, *, page: int, per_page: int):
        assert query_arg is query
        captured.append((page, per_page))
        window = build_pagination_window(total_items=0, page=page, per_page=per_page)
        return [], pagination_payload(window)

    monkeypatch.setattr(module, 'paginate_query', paginate)

    result = getattr(module, service_name)(page=3, per_page=25)

    assert captured == [(3, 25)]
    assert result[rows_key] == []
    assert result['pagination']['page'] == 1
    assert result['pagination']['per_page'] == 25
    assert result['pagination']['total_items'] == 0
