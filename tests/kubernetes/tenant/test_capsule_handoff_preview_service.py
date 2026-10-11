"""#1229: Capsule Release preview is a real but explicitly incomplete dry-run."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import capsule_handoff_preview_service as service
from app.kubernetes.tenant.release_handoff_approval import _plan_hash


def _plan():
    plan = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 2, 'provider': 'capsule',
        'requested_by': 42, 'requested_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': 'fingerprint', 'provider_identity': [{'uid': 'cr-1'}],
        'successor_owner': 'external-team', 'change_reference': 'CHG-2026-789',
        'handoff_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-1',
             'resource_version': '4', 'authority': 'capsule'},
            {'kind': 'Namespace', 'name': 'demo-dev', 'namespace': 'demo-dev',
             'uid': 'ns-1', 'resource_version': '6', 'authority': 'capsule'},
        ],
        'dependency_counts': {'Memberships': 0},
    }
    plan['plan_sha256'] = _plan_hash(plan)
    return plan


def _arrange(monkeypatch, *, changed=False):
    plan = _plan()
    approval = {
        'plan_sha256': plan['plan_sha256'],
        'status': 'acknowledged_pending_provider_handoff',
        'approved_at': datetime.now(UTC).isoformat(),
    }
    accepted = {'accepted_by': 43}
    tenant = SimpleNamespace(
        id='tenant-1', cluster_id='cluster-1', generation=2, provider_key='capsule',
        provider_state='capsule', reconciliation_authority='capsule',
        lifecycle_status='ready', ownership_status='adopted',
    )
    cluster = SimpleNamespace(id='cluster-1')
    calls = []
    class _Session:
        def get(self, model, key):
            return tenant if model is service.Tenant else cluster
        def add(self, event):
            calls.append(('audit', event.action))
        def commit(self):
            calls.append(('commit',))
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=_Session()))
    monkeypatch.setattr(service, 'require_platform_admin_actor', lambda actor: None)
    monkeypatch.setattr(service, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(service, 'latest_release_handoff_approval', lambda _: approval)
    monkeypatch.setattr(service, 'require_current_capsule_acceptance', lambda **_: accepted)
    monkeypatch.setattr(service, '_release_dependency_counts', lambda _: {'Memberships': 0})
    fresh = {
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'live_provider_identity': plan['provider_identity'],
        'handoff_components': plan['handoff_components'],
        'dependency_counts': plan['dependency_counts'],
        'capsule_related_inventory': {
            'blockers': [], 'global_quota': {'blockers': []},
            'rbac_lineage': {'blockers': []},
        },
    }
    if changed:
        fresh['handoff_fingerprint'] = 'other'
    monkeypatch.setattr(service, 'review_tenant_release_preflight_committed', lambda **_: fresh)
    monkeypatch.setattr(service, 'verify_capsule_provider_admin_authority', lambda **_: {
        'provider_username': 'admin', 'provider_groups': ['admins'],
        'provider_credential_id': 'X509SHA256=valid',
        'scope_count': 2, 'scoped_resources': ['cr', 'ns'],
    })
    accepted.update({
        'provider_username': 'admin', 'provider_groups': ['admins'],
        'provider_credential_id': 'X509SHA256=valid',
        'scope_count': 2, 'scoped_resources': ['cr', 'ns'],
    })
    adapter = SimpleNamespace(core_api=lambda: object(), custom_objects_api=lambda: object())
    monkeypatch.setattr(service.runtime_adapter, 'build_client', lambda _: adapter)
    def _preview(**kwargs):
        calls.append(('dry_run',))
        return {
            'status': 'preview_observed_coverage_incomplete',
            'dry_run_complete': False, 'provider_handoff_verified': False,
            'provider_mutation_performed': False, 'namespace_count': 1,
        }
    monkeypatch.setattr(service, 'preview_capsule_handoff_scope', _preview)
    return plan, accepted, calls


def test_accepting_actor_records_only_incomplete_server_preview(monkeypatch):
    plan, _, calls = _arrange(monkeypatch)
    result = service.preview_capsule_release_namespace_committed(
        tenant_id='tenant-1', actor_user_id=43, plan_sha256=plan['plan_sha256'],
        confirmed=True,
    )
    assert [item[0] for item in calls] == ['dry_run', 'audit', 'commit']
    assert result['status'] == 'namespace_server_dry_run_only'
    assert result['provider_execution_admitted'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert result['quota_limit_rbac_dry_run_verified'] is False


@pytest.mark.parametrize('case', ['unconfirmed', 'wrong_actor', 'drift', 'unexpected_ready'])
def test_fail_closed_without_provider_mutation_or_success_audit(monkeypatch, case):
    plan, accepted, calls = _arrange(monkeypatch, changed=case == 'drift')
    if case == 'unexpected_ready':
        monkeypatch.setattr(service, 'preview_capsule_handoff_scope', lambda **_: {
            'status': 'dry_run_passed', 'dry_run_complete': True,
            'provider_handoff_verified': True, 'provider_mutation_performed': False,
            'namespace_count': 1,
        })
    with pytest.raises(ValueError):
        service.preview_capsule_release_namespace_committed(
            tenant_id='tenant-1',
            actor_user_id=99 if case == 'wrong_actor' else 43,
            plan_sha256=plan['plan_sha256'],
            confirmed=case != 'unconfirmed',
        )
    assert not any(item[0] == 'audit' for item in calls)


def test_capsule_preview_route_retains_csrf_rbac_and_read_only_copy():
    source = Path('app/kubernetes/tenant/routes.py').read_text()
    section = source.split('def preview_capsule_release_namespace_route', 1)[1].split(
        "\n@tenant_bp.post", 1,
    )[0]
    assert '_csrf()' in section
    assert 'preview_capsule_release_namespace_committed' in section
    assert "detail='No live PATCH or governance Release was authorized." in section
    markup = Path('app/templates/kubernetes/tenant/partials/_tenant_management_detail.html').read_text()
    assert 'tenant.preview_capsule_release_namespace_route' in markup
    assert 'confirm_capsule_namespace_preview' in markup
    assert 'Quota, LimitRange, RoleBinding, and final Release are not yet admitted.' in markup
