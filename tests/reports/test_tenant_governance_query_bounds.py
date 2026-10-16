from types import SimpleNamespace

from sqlalchemy import column

from app.reports.export.payloads import tenant_governance as module


class QuerySpy:
    def __init__(self):
        self.calls = []

    def filter(self, *clauses):
        self.calls.append(('filter', tuple(str(clause) for clause in clauses)))
        return self

    def order_by(self, *clauses):
        self.calls.append(('order_by', tuple(str(clause) for clause in clauses)))
        return self

    def limit(self, limit):
        self.calls.append(('limit', limit))
        return self

    def all(self):
        self.calls.append(('all',))
        return []


def test_capacity_filter_runs_before_sql_limit(monkeypatch) -> None:
    query = QuerySpy()
    model = SimpleNamespace(
        query=query,
        cluster_id=column('cluster_id'),
        namespace=column('namespace'),
        created_at=column('created_at'),
    )
    monkeypatch.setattr(module, 'TenantCapacityDecision', model)
    result = module._capacity_decisions(SimpleNamespace(namespace='uat'), 'cluster-1')
    assert result == []
    assert [call[0] for call in query.calls] == ['filter', 'filter', 'order_by', 'limit', 'all']
    assert 'namespace' in query.calls[1][1][0]
    assert query.calls[-2] == ('limit', 250)


def test_audit_filter_runs_before_sql_limit_with_namespace_authority(monkeypatch) -> None:
    query = QuerySpy()
    model = SimpleNamespace(
        query=query,
        cluster_id=column('cluster_id'),
        tenant_id=column('tenant_id'),
        tenant_namespace_id=column('tenant_namespace_id'),
        kubernetes_namespace=column('kubernetes_namespace'),
        event_at=column('event_at'),
    )
    monkeypatch.setattr(module, 'TenantAuditEvidence', model)
    rows = module._scoped_audit_evidence(['tenant-1'], 'cluster-1', namespace='uat', namespace_ids={123})
    assert rows == []
    assert [call[0] for call in query.calls] == ['filter', 'filter', 'order_by', 'limit', 'all']
    # Namespace name and immutable namespace id are independent SQL clauses,
    # both applied before the 250-row audit window.
    name_predicate, id_predicate = query.calls[1][1]
    assert 'kubernetes_namespace' in name_predicate
    assert 'tenant_namespace_id' in id_predicate
    assert query.calls[-2] == ('limit', 250)
