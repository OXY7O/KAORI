from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.kubernetes.dashboard import service
from app.kubernetes.dashboard.sections import reporting


class _Column:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, value: object):
        return ('eq', self.name, value)

    def desc(self):
        return ('desc', self.name)


class _Query:
    def __init__(self, rows, predicates=(), order=(), limit=None):
        self.rows = rows
        self.predicates = predicates
        self.order = order
        self.row_limit = limit

    def filter(self, *predicates):
        return _Query(self.rows, (*self.predicates, *predicates), self.order, self.row_limit)

    def order_by(self, *order):
        return _Query(self.rows, self.predicates, order, self.row_limit)

    def limit(self, value):
        return _Query(self.rows, self.predicates, self.order, value)

    def _scoped(self):
        rows = [
            item
            for item in self.rows
            if all(getattr(item, name) == value for operator, name, value in self.predicates if operator == 'eq')
        ]
        if self.order:
            assert all(direction == 'desc' for direction, _name in self.order)
            rows.sort(key=lambda item: tuple(getattr(item, name) for _direction, name in self.order), reverse=True)
        return rows

    def all(self):
        rows = self._scoped()
        return rows if self.row_limit is None else rows[: self.row_limit]

    def count(self):
        return len(self._scoped())


def _model(rows, *, scope: bool = True, timestamp: bool = False):
    values = {
        'query': _Query(rows),
        'report_domain': _Column('report_domain'),
    }
    if scope:
        values['cluster_id'] = _Column('cluster_id')
    if timestamp:
        values['created_at'] = _Column('created_at')
        values['id'] = _Column('id')
    return SimpleNamespace(**values)


def test_kubernetes_reporting_excludes_foreign_domains_and_preserves_recency(monkeypatch) -> None:
    reports = [
        SimpleNamespace(
            id=1,
            name='Older Kubernetes',
            report_domain='kubernetes',
            cluster_id='cluster-a',
            created_at=datetime(2026, 10, 10, tzinfo=UTC),
            status='ready',
        ),
        SimpleNamespace(
            id=2,
            name='Foreign Registry',
            report_domain='registry',
            cluster_id=None,
            created_at=datetime(2026, 10, 23, tzinfo=UTC),
            status='ready',
        ),
        SimpleNamespace(
            id=3,
            name='Latest Kubernetes',
            report_domain='kubernetes',
            cluster_id='cluster-a',
            created_at=datetime(2026, 10, 22, tzinfo=UTC),
            status='ready',
        ),
        SimpleNamespace(
            id=4,
            name='Other Kubernetes Cluster',
            report_domain='kubernetes',
            cluster_id='cluster-b',
            created_at=datetime(2026, 10, 21, tzinfo=UTC),
            status='ready',
        ),
    ]
    templates = [
        SimpleNamespace(report_domain='kubernetes'),
        SimpleNamespace(report_domain='object_storage'),
    ]
    schedules = [
        SimpleNamespace(report_domain='kubernetes', cluster_id='cluster-a'),
        SimpleNamespace(report_domain='object_storage', cluster_id=None),
        SimpleNamespace(report_domain='kubernetes', cluster_id='cluster-b'),
    ]
    monkeypatch.setattr(reporting, 'Report', _model(reports, timestamp=True))
    monkeypatch.setattr(reporting, 'ReportTemplate', _model(templates, scope=False))
    monkeypatch.setattr(reporting, 'ReportSchedule', _model(schedules))

    fleet = reporting.build_reporting_snapshot(None)
    assert fleet.generated_reports == 3
    assert fleet.templates == 1
    assert fleet.schedules == 2
    assert [item.title for item in fleet.latest_reports] == [
        'Latest Kubernetes',
        'Other Kubernetes Cluster',
        'Older Kubernetes',
    ]

    selected = reporting.build_reporting_snapshot('cluster-a')
    assert selected.generated_reports == 2
    assert selected.templates == 1
    assert selected.schedules == 1
    assert [item.title for item in selected.latest_reports] == [
        'Latest Kubernetes',
        'Older Kubernetes',
    ]
    assert reporting.count_kubernetes_reports('cluster-b') == 1


def test_data_freshness_report_artifact_count_uses_kubernetes_scope(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        service,
        'count_kubernetes_reports',
        lambda cluster_id: calls.append(cluster_id) or 2,
    )
    monkeypatch.setattr(service, '_latest_inventory_sync', lambda _scope: None)
    monkeypatch.setattr(
        service,
        'count_records',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('Unscoped Report count')),
    )
    dashboard = SimpleNamespace(clusters=[], meta={}, data_freshness=[])

    service._populate_data_freshness(dashboard, selected_cluster_id=None, selected=None)

    assert calls == [None]
    report_tile = next(item for item in dashboard.data_freshness if item.label == 'Report Artifacts')
    assert report_tile.value == '1 retained artifact record'
    assert report_tile.status == 'Recorded'
