from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.binding_selectors import BindingSelectorError
from app.storage.object_storage.analytics import alert_sources


class _Rows:
    def __init__(self, rows):
        self.rows = rows
        self.filter_clauses = []

    def filter(self, *clauses):
        self.filter_clauses.append(clauses)
        return self

    def all(self):
        return self.rows


def _bindings(monkeypatch, rows):
    # Flask-SQLAlchemy's Model.query descriptor requires an app context.
    # Replace this module's imported model for a pure scope unit test;
    # preserve the real column comparator objects for all four predicates.
    model = alert_sources.IntegrationBinding
    query = _Rows(rows)
    monkeypatch.setattr(
        alert_sources,
        'IntegrationBinding',
        SimpleNamespace(
            query=query,
            integration_instance_id=model.integration_instance_id,
            asset_type=model.asset_type,
            enabled=model.enabled,
            id=model.id,
        ),
    )
    return query


def _consumer(selector, peers=()):
    return SimpleNamespace(
        binding=SimpleNamespace(
            id=1,
            integration_instance_id=8,
            selector_json=selector,
        )
    )


def test_metrics_alert_scope_restricts_promql_to_asset_identity(monkeypatch) -> None:
    query = _bindings(monkeypatch, [])
    expression = alert_sources._scoped_metrics_alert_expression(
        _consumer({'matchers': [{'label': 'instance', 'operator': '=', 'value': 'storage-a:9000'}]})
    )
    assert 'ALERTS{' in expression
    assert 'instance="storage-a:9000"' in expression
    assert 'alertstate=~"pending|firing"' in expression
    assert len(query.filter_clauses) == 1
    assert len(query.filter_clauses[0]) == 4


@pytest.mark.parametrize(
    'selector',
    [
        None,
        {'matchers': []},
        {'matchers': [{'label': 'job', 'operator': '=~', 'value': 'minio.*'}]},
    ],
)
def test_missing_or_regex_only_identity_fails_closed(selector) -> None:
    with pytest.raises(BindingSelectorError, match='exact asset label'):
        alert_sources._scoped_metrics_alert_expression(_consumer(selector))


def test_shared_metrics_source_duplicate_scope_is_not_attributed_to_both_systems(monkeypatch) -> None:
    selected = {'matchers': [{'label': 'instance', 'operator': '=', 'value': 'storage-a'}]}
    peer = SimpleNamespace(selector_json=selected)
    query = _bindings(monkeypatch, [peer])
    with pytest.raises(BindingSelectorError, match='overlap'):
        alert_sources._scoped_metrics_alert_expression(_consumer(selected))
    assert len(query.filter_clauses) == 1
    assert len(query.filter_clauses[0]) == 4


def test_two_systems_with_disjoint_exact_selectors_are_eligible(monkeypatch) -> None:
    first = {'matchers': [{'label': 'instance', 'operator': '=', 'value': 'storage-a'}]}
    second = {'matchers': [{'label': 'instance', 'operator': '=', 'value': 'storage-b'}]}
    query = _bindings(monkeypatch, [SimpleNamespace(selector_json=second)])
    expression = alert_sources._scoped_metrics_alert_expression(_consumer(first))
    assert 'instance="storage-a"' in expression
    assert 'instance="storage-b"' not in expression
    assert len(query.filter_clauses) == 1
    assert len(query.filter_clauses[0]) == 4
