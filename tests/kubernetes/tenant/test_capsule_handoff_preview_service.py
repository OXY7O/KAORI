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
    def _preview_related(**kwargs):
        calls.append(('related_dry_run',))
        return {'related_preview_count': 1, 'related_preserved_count': 0}
    monkeypatch.setattr(service, '_preview_related_provider_scope', _preview_related)
    return plan, accepted, calls


def test_accepting_actor_records_only_incomplete_server_preview(monkeypatch):
    plan, _, calls = _arrange(monkeypatch)
    result = service.preview_capsule_release_namespace_committed(
        tenant_id='tenant-1', actor_user_id=43, plan_sha256=plan['plan_sha256'],
        confirmed=True,
    )
    assert [item[0] for item in calls] == ['dry_run', 'related_dry_run', 'audit', 'commit']
    assert result['status'] == 'complete_scope_server_dry_run_only'
    assert result['provider_execution_admitted'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert result['quota_limit_rbac_dry_run_verified'] is False
    assert result['related_preview_count'] == 1
    assert result['whole_scope_source_unchanged'] is True


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
    assert 'Preview Capsule provider handoff' in markup
    assert 'Preview is not transfer approval, PATCH execution or governance Release.' in markup


def test_related_scope_previews_only_exact_kaori_candidates_and_reads_foreign(monkeypatch):
    candidate = {
        'kind': 'ResourceQuota', 'namespace': 'demo-dev', 'name': 'quota',
        'uid': 'quota-uid', 'resource_version': '7',
        'origin': 'kaori_correlated',
    }
    preserved = {
        'kind': 'LimitRange', 'namespace': 'demo-dev', 'name': 'external-limit',
        'uid': 'limit-uid', 'resource_version': '8',
        'origin': 'foreign_preserved',
    }
    decisions = [
        {'kind': 'CapsuleTenant', 'namespace': '', 'name': 'demo',
         'decision': 'provider_cr_preservation_review_required'},
        {**candidate, 'decision': 'explicit_kaori_metadata_handoff_review'},
        {**preserved, 'decision': 'preserve_foreign_provider_control'},
    ]
    monkeypatch.setattr(
        service, 'build_capsule_handoff_worklist',
        lambda **_: {'items': decisions},
    )
    calls = []
    def read(**kwargs):
        calls.append(('read', kwargs['name']))
        return {
            'metadata': {'labels': {
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-1',
            }},
        }
    core = SimpleNamespace(
        read_namespaced_resource_quota=read,
        read_namespaced_limit_range=read,
    )
    rbac = SimpleNamespace(read_namespaced_role_binding=read)
    provider = SimpleNamespace(core_api=lambda: core, rbac_authorization_api=lambda: rbac)
    def classify(*, kind, **kwargs):
        record = candidate if kind == 'ResourceQuota' else preserved
        findings = (
            ['Capsule ResourceQuota/demo-dev/quota retains KAORI provider controls '
             'requiring separately admitted handoff.']
            if kind == 'ResourceQuota' else []
        )
        return record, findings
    monkeypatch.setattr(service, 'classify_capsule_related_resource', classify)
    def sar(**kwargs):
        calls.append(('sar', kwargs['candidates'][0]['name']))
        return {'checked_count': 1}
    monkeypatch.setattr(service, 'verify_capsule_related_admin_authority', sar)
    def preview(**kwargs):
        calls.append(('preview', kwargs['record']['name'], kwargs['approved_label_keys']))
        return {
            'status': 'server_dry_run_shape_observed_not_execution_admitted',
            'live_resource_unchanged': True, 'provider_mutation_performed': False,
            'provider_execution_admitted': False,
        }
    monkeypatch.setattr(service, 'preview_capsule_related_handoff_with_provider', preview)
    plan = {
        'tenant_id': 'tenant-1', 'successor_owner': 'platform-team',
        'handoff_components': [{'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid'}],
    }
    result = service._preview_related_provider_scope(
        provider=provider, plan=plan, related={'resources': [candidate, preserved]},
    )
    assert result == {'related_preview_count': 1, 'related_preserved_count': 1}
    assert ('sar', 'quota') in calls
    assert ('preview', 'quota', ['app.kubernetes.io/managed-by', 'kaori.io/tenant-id']) in calls
    assert ('read', 'external-limit') in calls
    assert not any(item[0] == 'preview' and item[1] == 'external-limit' for item in calls)


def test_related_scope_refuses_unapproved_provider_origin_without_get_or_patch(monkeypatch):
    monkeypatch.setattr(service, 'build_capsule_handoff_worklist', lambda **_: {
        'items': [{'kind': 'RoleBinding', 'namespace': 'demo-dev', 'name': 'ambiguous',
                   'decision': 'operator_origin_investigation'}],
    })
    with pytest.raises(ValueError, match='ambiguous origin'):
        service._preview_related_provider_scope(
            provider=SimpleNamespace(), plan={'handoff_components': []},
            related={'resources': []},
        )


def test_complete_preview_refuses_source_mutation_even_after_successful_dryrun(monkeypatch):
    plan, _, calls = _arrange(monkeypatch)
    invocations = iter([
        {
            'handoff_fingerprint': plan['handoff_fingerprint'],
            'live_provider_identity': plan['provider_identity'],
            'handoff_components': plan['handoff_components'],
            'dependency_counts': plan['dependency_counts'],
            'capsule_related_inventory': {
                'blockers': [], 'global_quota': {'blockers': []},
                'rbac_lineage': {'blockers': []},
            },
        },
        {'handoff_fingerprint': 'changed-mid-preview'},
    ])
    monkeypatch.setattr(
        service, 'review_tenant_release_preflight_committed',
        lambda **_: next(invocations),
    )
    with pytest.raises(ValueError, match='changed during complete-scope dry-run'):
        service.preview_capsule_release_namespace_committed(
            tenant_id='tenant-1', actor_user_id=43, plan_sha256=plan['plan_sha256'],
            confirmed=True,
        )
    assert [item[0] for item in calls] == ['dry_run', 'related_dry_run']
