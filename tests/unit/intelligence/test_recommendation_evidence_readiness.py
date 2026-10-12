from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.intelligence import tenant_governance_recommendations as tenant
from app.intelligence.object_storage_recommendations import _provider_identity
from app.intelligence.service import classify_recommendation_readiness


def test_evaluator_errors_never_mean_healthy_empty_results() -> None:
    assert classify_recommendation_readiness(
        total=2, recent=2, issues=['Tenant Governance'], has_findings=False
    ) == 'unavailable'
    assert classify_recommendation_readiness(
        total=2, recent=2, issues=['Tenant Governance'], has_findings=True
    ) == 'partial'
    assert classify_recommendation_readiness(
        total=3, recent=1, issues=[], has_findings=False
    ) == 'partial'
    assert classify_recommendation_readiness(
        total=0, recent=0, issues=[], has_findings=False
    ) == 'not_collected'
    assert classify_recommendation_readiness(
        total=2, recent=2, issues=[], has_findings=False
    ) == 'baseline_recent'


def test_disabled_or_retired_storage_provider_fails_closed() -> None:
    asset = SimpleNamespace(id='storage-1')
    def identity(*, enabled: bool, lifecycle_status: str):
        return SimpleNamespace(
            enabled=enabled, lifecycle_status=lifecycle_status, provider_key='minio',
            metadata_json={'provider_label': 'MinIO'},
        )
    assert _provider_identity(asset, {'storage-1': identity(enabled=False, lifecycle_status='active')})[0] == ''
    assert _provider_identity(asset, {'storage-1': identity(enabled=True, lifecycle_status='retired')})[0] == ''
    assert _provider_identity(asset, {'storage-1': identity(enabled=True, lifecycle_status='active')})[0] == 'minio'


def test_tenant_evaluator_sql_failure_is_not_silently_converted_to_no_findings(monkeypatch) -> None:
    def failed(_rules):
        raise SQLAlchemyError('simulated database failure')
    monkeypatch.setattr(tenant, '_credential_findings', failed)
    with pytest.raises(SQLAlchemyError):
        tenant.build_tenant_governance_recommendation_findings({})


def test_historical_tenant_events_do_not_become_current_recommendations(monkeypatch) -> None:
    def skipped(_rules):
        raise AssertionError('history must remain in audit, not active recommendations')
    for name in ('_audit_findings', '_policy_event_findings'):
        monkeypatch.setattr(tenant, name, skipped)
    for name in (
        '_credential_findings', '_access_findings', '_access_declaration_findings',
        '_namespace_findings', '_managed_resource_findings', '_provider_findings',
        '_capacity_findings',
    ):
        monkeypatch.setattr(tenant, name, lambda _rules: [])
    assert tenant.build_tenant_governance_recommendation_findings({}) == []
