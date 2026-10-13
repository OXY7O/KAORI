from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.intelligence.alert_intelligence import recommendation_source as source


def test_tls_missing_finding_is_unknown_without_successful_current_tls_collection(monkeypatch) -> None:
    monkeypatch.setattr(source, '_source_evidence_posture', lambda **kwargs: (True, ''))
    monkeypatch.setattr(source, 'catalog_rule', lambda _rule: {})
    state = SimpleNamespace(
        rule_key='kubernetes.tls_secret.expired',
        asset_key='cluster-1',
        domain='kubernetes',
    )
    collection = SimpleNamespace(
        secret_collection_status='collection_failed',
        collected_at=datetime.now(UTC),
    )
    monkeypatch.setattr(
        source,
        'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda *_args: collection)),
    )
    assert source._source_evidence_posture_for_state(state) == (False, 'source_unavailable')
    collection.secret_collection_status = source.TLS_COLLECTION_COLLECTED
    collection.collected_at = datetime.now(UTC) - timedelta(days=2)
    assert source._source_evidence_posture_for_state(state) == (False, 'source_unavailable')
    collection.collected_at = datetime.now(UTC)
    assert source._source_evidence_posture_for_state(state) == (True, '')


def test_unknown_source_never_counts_as_explicit_resolution() -> None:
    from app.common.alert_case_source_state import is_active_alert_case

    case = SimpleNamespace(
        source_type='recommendation',
        source_state='unknown',
        workflow_state='open',
    )
    assert is_active_alert_case(case)
    case.source_state = 'resolved'
    assert not is_active_alert_case(case)


def test_missing_finding_with_unavailable_source_stays_unknown_not_resolved(monkeypatch) -> None:
    state = SimpleNamespace(
        finding_key='registry.security.critical_runtime_vulnerability:42',
        active=True,
        alert_case_id=42,
    )
    alert_case = SimpleNamespace(workflow_state='open')
    observed = []

    class StateQuery:
        def filter_by(self, **kwargs):
            assert kwargs == {'active': True}
            return self

        def all(self):
            return [state]

    monkeypatch.setattr(source, '_active_recommendation_state_batches', lambda: iter([state]))
    monkeypatch.setattr(source, '_source_evidence_posture_for_state', lambda _state: (False, 'source_unavailable'))
    monkeypatch.setattr(
        source,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(get=lambda *_args: alert_case),
        ),
    )
    monkeypatch.setattr(
        source,
        'mark_case_source_unknown',
        lambda case, **kwargs: observed.append((case, kwargs['reason'])) or True,
    )
    stats = {'source_unknown': 0, 'resolved': 0}
    source._reconcile_missing_recommendation_states(
        fresh_keys=set(),
        now=datetime.now(UTC),
        stats=stats,
    )
    assert state.active is True
    assert stats['resolved'] == 0
    assert stats['source_unknown'] == 1
    assert observed == [(alert_case, 'source_unavailable')]


def test_capacity_forecast_can_clear_only_after_usable_fresh_projection(monkeypatch) -> None:
    monkeypatch.setattr(source, '_source_evidence_posture', lambda **_kwargs: (True, ''))
    monkeypatch.setattr(source, 'catalog_rule', lambda _rule: {})
    state = SimpleNamespace(
        rule_key='object_storage.forecast.capacity_exhaustion_critical',
        asset_key='storage-1',
        domain='object_storage',
    )
    stale_or_absent = SimpleNamespace(
        payload_json={'forecast': {'days_to_capacity': 100, 'growth_per_day': 1}},
    )

    class Column:
        def __eq__(self, other):
            return True

        def __gt__(self, other):
            return True

    class ForecastQuery:
        row = None

        def filter(self, *_criteria):
            return self

        def first(self):
            return self.row

    query = ForecastQuery()
    monkeypatch.setattr(
        source,
        'ObjectStorageForecastSnapshot',
        SimpleNamespace(
            query=query,
            object_storage_system_id=Column(),
            history_window=Column(),
            method=Column(),
            status=Column(),
            expires_at=Column(),
        ),
    )
    assert source._source_evidence_posture_for_state(state) == (False, 'source_unavailable')
    query.row = stale_or_absent
    assert source._source_evidence_posture_for_state(state) == (True, '')
    query.row = SimpleNamespace(payload_json={'forecast': {'days_to_capacity': None}})
    assert source._source_evidence_posture_for_state(state) == (False, 'source_unavailable')


def test_active_recommendation_state_reader_uses_bounded_keyset_pages(monkeypatch) -> None:
    rows = [SimpleNamespace(id=i) for i in range(1, 206)]
    pages = []

    class Column:
        def is_(self, _value):
            return True

        def __gt__(self, value):
            return ('after', value)

        def asc(self):
            return self

    class Query:
        after = 0
        limit_size = 0

        def filter(self, *criteria):
            self.after = next((item[1] for item in criteria if isinstance(item, tuple) and item[0] == 'after'), 0)
            return self

        def order_by(self, *_columns):
            return self

        def limit(self, count):
            self.limit_size = count
            return self

        def all(self):
            page = [row for row in rows if row.id > self.after][: self.limit_size]
            pages.append(len(page))
            return page

    monkeypatch.setattr(
        source,
        'RecommendationAlertState',
        SimpleNamespace(query=Query(), active=Column(), id=Column()),
    )
    assert len(list(source._active_recommendation_state_batches())) == 205
    assert pages == [200, 5, 0]
