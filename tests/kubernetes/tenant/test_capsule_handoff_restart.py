"""#1228 Capsule G1 expired acknowledged-plan restart (source-authored, not run)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import capsule_handoff_restart as restart
from app.kubernetes.tenant.release_handoff_approval import _plan_hash


def _plan(*, elapsed_minutes=30):
    requested = (datetime.now(UTC) - timedelta(minutes=elapsed_minutes)).isoformat()
    values = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 1, 'provider': 'capsule',
        'handoff_fingerprint': 'b' * 64,
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'demo',
             'uid': 'cr-uid', 'resource_version': '5'},
            {'kind': 'Namespace', 'name': 'demo-dev',
             'uid': 'ns-uid', 'resource_version': '11'},
        ],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-2026-009',
        'requested_by': 17, 'requested_at': requested,
    }
    return {
        **values, 'plan_sha256': _plan_hash(values),
        'status': 'pending_independent_approval',
        'handoff_components': [],
    }


def _review(plan, *, elapsed_minutes=30):
    return {
        'plan_sha256': plan['plan_sha256'],
        'requested_by': 17,
        'approved_by': 31,
        'status': 'acknowledged_pending_provider_handoff',
        'approved_at': (
            datetime.now(UTC) - timedelta(minutes=elapsed_minutes)
        ).isoformat(),
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'provider_handoff_verified': False,
        'release_authorized': False,
    }


def test_capsule_expired_acknowledged_plan_denies_wrong_actor_unexpired_or_forged_scope():
    plan = _plan()
    approved = _review(plan)
    restart._assert_expired_acknowledged_capsule(
        tenant_id='tenant-1', actor_user_id=17,
        plan_sha256=plan['plan_sha256'], plan=plan, approval=approved,
    )
    for actor_id, p, decision, match in [
        (31, plan, approved, 'Only the original requester'),
        (17, _plan(elapsed_minutes=1), None, 'Only the original requester'),
    ]:
        if decision is None:
            decision = _review(p, elapsed_minutes=1)
        with pytest.raises(ValueError, match=match if actor_id == 31 else 'still current'):
            restart._assert_expired_acknowledged_capsule(
                tenant_id='tenant-1', actor_user_id=actor_id,
                plan_sha256=p['plan_sha256'], plan=p, approval=decision,
            )
    bad = {**plan, 'successor_owner': 'attacker'}
    with pytest.raises(ValueError, match='exact independently acknowledged'):
        restart._assert_expired_acknowledged_capsule(
            tenant_id='tenant-1', actor_user_id=17,
            plan_sha256=plan['plan_sha256'], plan=bad, approval=approved,
        )


def test_capsule_restart_missing_confirmation_denies_every_other_call(monkeypatch):
    monkeypatch.setattr(restart, 'latest_release_handoff_plan',
                        lambda _: pytest.fail('No source read without confirmation'))
    with pytest.raises(ValueError, match='Explicit Capsule'):
        restart.restart_expired_capsule_handoff_plan_committed(
            tenant_id='tenant-1', actor_user_id=17,
            plan_sha256='a' * 64, confirmed=False,
        )


def test_capsule_restart_requires_postgresql_and_protected_ledger(monkeypatch):
    monkeypatch.setattr(restart, 'db', SimpleNamespace(
        session=SimpleNamespace(
            get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='sqlite'))
        ),
    ))
    with pytest.raises(ValueError, match='protected PostgreSQL'):
        restart._ensure_capsule_no_execution_history('tenant-1')

    calls = []
    session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
    )
    monkeypatch.setattr(restart, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(restart, '_require_postgres_ledger_write_once_guards',
                        lambda s: calls.append(s))
    class _Query:
        def filter_by(self, **kwargs):
            return self
        def limit(self, n):
            assert n == 1
            return self
        def first(self):
            return SimpleNamespace(id=1)
    monkeypatch.setattr(restart, 'CapsuleHandoffLedgerEvent',
                        SimpleNamespace(query=_Query()))
    with pytest.raises(ValueError, match='START/attempt history'):
        restart._ensure_capsule_no_execution_history('tenant-1')
    assert calls == [session]


def _stage(monkeypatch, *, changed_scope=False, changed_generation=False):
    plan = _plan()
    approval = _review(plan)
    receipt_events = []
    calls = []
    monkeypatch.setattr(restart, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(restart, 'latest_release_handoff_approval', lambda _: approval)
    monkeypatch.setattr(restart, '_ensure_capsule_no_execution_history',
                        lambda _: calls.append('no-attempt-read'))
    monkeypatch.setattr(restart, '_complete_provider_snapshot', lambda _: calls.append('snapshot'))
    monkeypatch.setattr(restart, '_can_confirm_plan', lambda _: calls.append('g1-review'))
    snapshot = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 2 if changed_generation else 1,
        'provider': 'capsule',
        'handoff_fingerprint': 'c' * 64 if changed_scope else 'b' * 64,
        'live_provider_identity': plan['provider_identity'],
        'handoff_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
             'resource_version': '5'},
        ],
        'dependency_counts': {},
        'blockers': [
            'Capsule allocation was modified by KAORI; explicit provider authority handoff is required.',
        ],
    }
    monkeypatch.setattr(
        restart, 'review_tenant_release_preflight_committed',
        lambda **_: snapshot,
    )
    tenant = SimpleNamespace(
        lifecycle_status='ready', ownership_status='adopted',
        provider_key='capsule', provider_state='capsule',
        reconciliation_authority='capsule',
        cluster_id='cluster-1', generation=1,
    )
    class _TenantQuery:
        def filter_by(self, **kwargs):
            return self
        def with_for_update(self):
            return self
        def one_or_none(self):
            return tenant
    monkeypatch.setattr(restart, 'Tenant', SimpleNamespace(query=_TenantQuery()))
    class _Session:
        def add(self, row):
            receipt_events.append(row)
        def commit(self):
            calls.append('commit')
    monkeypatch.setattr(restart, 'db', SimpleNamespace(session=_Session()))
    monkeypatch.setattr(restart, 'AuditEvent', lambda **kwargs: kwargs)
    return plan, approval, calls, receipt_events


def test_capsule_expired_plan_restarts_only_after_two_no_attempt_checks_and_fresh_preflight(monkeypatch):
    plan, _, calls, events = _stage(monkeypatch, changed_scope=True)
    new = restart.restart_expired_capsule_handoff_plan_committed(
        tenant_id='tenant-1', actor_user_id=17,
        plan_sha256=plan['plan_sha256'], confirmed=True,
    )
    assert calls == [
        'no-attempt-read', 'snapshot', 'g1-review', 'no-attempt-read', 'commit',
    ]
    assert len(events) == 1
    assert events[0]['target_type'] == 'kubernetes_tenant_release_handoff_plan'
    assert events[0]['action'] == 'tenant.release.capsule_expired_plan_restarted'
    assert new['supersedes_plan_sha256'] == plan['plan_sha256']
    assert new['plan_sha256'] != plan['plan_sha256']
    assert new['handoff_fingerprint'] == 'c' * 64
    assert new['requested_by'] == 17
    assert new['status'] == 'pending_independent_approval'
    assert new['provider_mutation_performed'] is False
    assert new['provider_handoff_verified'] is False
    assert new['release_authorized'] is False
    assert new['secret_material_persisted'] is False


def test_capsule_restart_denies_changed_cluster_or_generation(monkeypatch):
    plan, _, calls, events = _stage(monkeypatch, changed_generation=True)
    with pytest.raises(ValueError, match='identity changed'):
        restart.restart_expired_capsule_handoff_plan_committed(
            tenant_id='tenant-1', actor_user_id=17,
            plan_sha256=plan['plan_sha256'], confirmed=True,
        )
    assert 'commit' not in calls
    assert events == []


def test_capsule_expired_review_ui_is_not_presented_as_valid_platform_admin_approval():
    from pathlib import Path
    from jinja2 import Environment

    source = Path(
        'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html'
    ).read_text(encoding='utf-8')
    Environment(autoescape=True).parse(source)
    assert 'row.capsule_approved_plan_expired' in source
    assert 'Capsule independent approval expired' in source
    assert 'Restart Expired Capsule Plan' in source
    assert 'not row.capsule_approved_plan_expired' in source
    assert "tenant.restart_expired_capsule_handoff_route" in source
    assert 'confirm_capsule_handoff_restart' in source


def test_capsule_restart_route_is_review_only_and_independently_permission_gated():
    from pathlib import Path
    source = Path('app/kubernetes/tenant/routes.py').read_text()
    assert "def restart_expired_capsule_handoff_route(tenant_id: str):" in source
    assert "'/tenants/<string:tenant_id>/release-handoff/capsule-restart-expired'" in source
    assert "restart_expired_capsule_handoff_plan_committed(" in source
