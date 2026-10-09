from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.intelligence import tenant_governance_recommendations as recommendations


@pytest.mark.parametrize('code', [
    'revoked_grant_still_declared',
    'active_grant_missing_capsule_declaration',
    'active_grant_missing_native_declaration',
    'native_grant_scope_mismatch',
    'native_grant_role_reference_mismatch',
])
def test_known_grant_declaration_drift_reuses_existing_intelligence_rule(code):
    assert recommendations.access_declaration_rule_key(code) == (
        'kubernetes.tenant.access.grant_drift'
    )


@pytest.mark.parametrize('code', [
    'external_capsule_owner', 'external_access_review',
    'external_native_rolebinding', 'unverified_kaori_grant_marker',
    'orphaned_kaori_grant_marker', 'unresolved_native_rolebinding_ownership',
    '', 'unknown_external_principal',
])
def test_foreign_subject_is_not_misrepresented_as_audit_verified_unmanaged_principal(code):
    assert recommendations.access_declaration_rule_key(code) is None


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def filter_by(self, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def limit(self, count):
        return _Query(self.rows[:count])

    def all(self):
        return self.rows


class _Column:
    def in_(self, values):
        return values

    def desc(self):
        return self


def _event(*, status='review_required', code='revoked_grant_still_declared', age=0, event_id=14):
    return SimpleNamespace(
        id=event_id,
        target_type='kubernetes_tenant_native_access_drift_evidence',
        metadata_json={
            'tenant_id': 'tenant-a',
            'cluster_id': 'cluster-a',
            'status': status,
            'effective_rbac_verified': False,
            'evaluated_at': (datetime.now(UTC) - timedelta(seconds=age)).isoformat(),
            'source_observed_at': datetime.now(UTC).isoformat(),
            'source_evidence_sha256': 'a' * 64,
            'findings': [
                {'code': code, 'severity': 'critical', 'subject': 'grant-1'},
                {'code': 'external_native_rolebinding', 'subject': 'foreign-binding'},
            ],
        },
    )


def _setup(monkeypatch, events):
    tenant = SimpleNamespace(
        id='tenant-a', name='sandbox', cluster_id='cluster-a',
        provider_key='native_kubernetes', lifecycle_status='ready',
    )
    monkeypatch.setattr(
        recommendations, 'AuditEvent',
        SimpleNamespace(query=_Query(events), target_type=_Column(), id=_Column()),
    )
    monkeypatch.setattr(
        recommendations, 'Tenant',
        SimpleNamespace(query=_Query([tenant])),
    )


def _rules():
    return {
        'kubernetes.tenant.access.grant_drift': {
            'rule_key': 'kubernetes.tenant.access.grant_drift',
            'domain': 'kubernetes',
            'severity': 'warning',
        }
    }


def test_committed_native_grant_declaration_is_projected_to_one_existing_rule(monkeypatch):
    _setup(monkeypatch, [_event()])
    rows = recommendations._access_declaration_findings(_rules())

    assert len(rows) == 1
    assert rows[0]['rule_key'].startswith('kubernetes.tenant.access.grant_drift:')
    assert rows[0]['evidence']['declaration_code'] == 'revoked_grant_still_declared'
    assert rows[0]['evidence']['effective_rbac_verified'] is False
    assert rows[0]['evidence']['source_event_id'] == 14


def test_latest_resolved_evidence_supersedes_old_drift(monkeypatch):
    _setup(monkeypatch, [_event(status='no_declaration_findings', event_id=15), _event()])
    assert recommendations._access_declaration_findings(_rules()) == []


def test_stale_declaration_does_not_claim_current_risk(monkeypatch):
    _setup(monkeypatch, [_event(age=7200)])
    assert recommendations._access_declaration_findings(_rules()) == []


def test_only_foreign_binding_does_not_generate_fabricated_grant_drift(monkeypatch):
    _setup(monkeypatch, [_event(code='external_native_rolebinding')])
    assert recommendations._access_declaration_findings(_rules()) == []
