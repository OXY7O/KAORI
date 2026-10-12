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
        source, 'db',
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
        source_type='recommendation', source_state='unknown', workflow_state='open',
    )
    assert is_active_alert_case(case)
    case.source_state = 'resolved'
    assert not is_active_alert_case(case)
