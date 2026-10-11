"""#1229: disabled Capsule PATCH adapter contracts (authored, NOT executed)."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import capsule_handoff_live_patch as live


def _component(kind='Namespace'):
    return {
        'kind': kind, 'name': 'demo-dev' if kind == 'Namespace' else 'quota',
        'namespace': 'demo-dev', 'uid': 'provider-uid',
        'resource_version': '7', 'authority': 'capsule',
        'handoff': 'external_acceptance_required',
        'ownership': 'kaori_marker_correlated',
    }


def _metadata(resource_version='7', *, owner='kaori'):
    return SimpleNamespace(
        name='demo-dev', uid='provider-uid',
        resource_version=resource_version,
        labels={
            'app.kubernetes.io/managed-by': owner,
            'kaori.io/tenant-id': 'tenant-1',
            'capsule.clastix.io/tenant': 'demo',
        },
        annotations={}, owner_references=[], finalizers=[],
        generation=1, deletion_timestamp=None,
        deletion_grace_period_seconds=None,
    )


def test_capsule_live_patch_is_statically_disabled_before_any_provider_call():
    class _Forbidden:
        def __getattr__(self, name):
            raise AssertionError(f'Unexpected provider access: {name}')
    with pytest.raises(PermissionError, match='disabled pending durable START'):
        live.execute_capsule_single_metadata_patch_staged(
            core=_Forbidden(), rbac=_Forbidden(),
            component=_component(), tenant_id='tenant-1',
            capsule_name='demo', capsule_uid='cr-uid',
            successor_owner='platform-team',
        )
    assert live._CAPSULE_LIVE_PATCH_ENABLED is False


@pytest.mark.parametrize(('kind', 'method'), [
    ('Namespace', 'patch_namespace'),
    ('ResourceQuota', 'patch_namespaced_resource_quota'),
    ('LimitRange', 'patch_namespaced_limit_range'),
    ('RoleBinding', 'patch_namespaced_role_binding'),
])
def test_capsule_patch_dispatch_is_typed_and_never_infers_a_spec_write(kind, method):
    calls = []
    def invoke(**kwargs):
        calls.append(kwargs)
        return {'provider': 'example'}
    class _Provider:
        def __getattr__(self, name):
            if name == method or name == method.replace('patch_', 'read_', 1):
                return invoke
            raise AssertionError(name)
    core, rbac = _Provider(), _Provider()
    _, dispatcher = live._provider_methods(core=core, rbac=rbac, kind=kind)
    operations = [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'provider-uid'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '7'},
    ]
    first = live._provider_patch(
        dispatcher, kind=kind, name='quota', namespace='demo-dev',
        body=operations, dry_run=True,
    )
    second = live._provider_patch(
        dispatcher, kind=kind, name='quota', namespace='demo-dev',
        body=operations, dry_run=False,
    )
    assert first == second == {'provider': 'example'}
    assert calls[0]['dry_run'] == 'All'
    assert 'dry_run' not in calls[1]
    assert all(c['body'] == operations for c in calls)
    assert all(c['_content_type'] == 'application/json-patch+json' for c in calls)
    assert all('spec' not in c for c in calls)
    if kind == 'Namespace':
        assert all('namespace' not in c for c in calls)
    else:
        assert all(c['namespace'] == 'demo-dev' for c in calls)


def test_capsule_before_patch_detects_namespace_uid_rv_or_label_drift(monkeypatch):
    monkeypatch.setattr(live, 'capsule_preservation_digest', lambda obj: obj.spec)
    before = SimpleNamespace(metadata=_metadata(), spec={'quota': 'unchanged'})
    same = deepcopy(before)
    live._require_source_still_unchanged(
        kind='Namespace', before=before, current=same,
        record=_component(), tenant_id='tenant-1',
        capsule_name='demo', capsule_uid='cr-uid',
    )
    cases = [
        lambda r: setattr(r.metadata, 'resource_version', '8'),
        lambda r: r.metadata.labels.update({'third-party/extra': 'unexpected'}),
        lambda r: r.spec.update({'quota': 'mutated'}),
    ]
    for mutation in cases:
        changed = deepcopy(before)
        mutation(changed)
        with pytest.raises(ValueError, match='changed during live dry-run'):
            live._require_source_still_unchanged(
                kind='Namespace', before=before, current=changed,
                record=_component(), tenant_id='tenant-1',
                capsule_name='demo', capsule_uid='cr-uid',
            )


def test_capsule_live_candidate_cannot_treat_preview_as_release(monkeypatch):
    # Synthetic unit case only: no Kubernetes or database access.
    monkeypatch.setattr(live, '_CAPSULE_LIVE_PATCH_ENABLED', True)
    calls = []
    before = SimpleNamespace(metadata=_metadata(), spec={})
    after = SimpleNamespace(metadata=_metadata('8', owner='platform-team'), spec={})
    provider_state = {'transferred': False}

    class _Core:
        def read_namespace(self, **kwargs):
            calls.append(('read', kwargs))
            return deepcopy(after if provider_state['transferred'] else before)

        def patch_namespace(self, **kwargs):
            calls.append(('patch', kwargs))
            if kwargs.get('dry_run') == 'All':
                return deepcopy(after)
            provider_state['transferred'] = True
            return deepcopy(after)

    monkeypatch.setattr(
        live, 'capture_capsule_namespace_baseline',
        lambda *args, **kwargs: {'kind': 'Namespace'},
    )
    monkeypatch.setattr(
        live, 'build_capsule_namespace_handoff_patch',
        lambda *args, **kwargs: [
            {'op': 'test', 'path': '/metadata/uid', 'value': 'provider-uid'},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '7'},
        ],
    )
    monkeypatch.setattr(live, 'verify_capsule_namespace_preview', lambda **_: None)
    monkeypatch.setattr(live, 'capsule_preservation_digest', lambda obj: obj.spec)
    monkeypatch.setattr(
        live, 'classify_capsule_namespace_handoff',
        lambda **_: {'state': 'provider_markers_transferred', 'resource_version': '8'},
    )
    result = live.execute_capsule_single_metadata_patch_staged(
        core=_Core(), rbac=SimpleNamespace(), component=_component(),
        tenant_id='tenant-1', capsule_name='demo',
        capsule_uid='cr-uid', successor_owner='platform-team',
    )
    assert [c[0] for c in calls] == ['read', 'patch', 'read', 'patch', 'read']
    assert calls[1][1]['dry_run'] == 'All'
    assert 'dry_run' not in calls[3][1]
    assert result['status'] == 'single_object_metadata_transfer_observed_not_full_handoff'
    assert result['provider_mutation_performed'] is True
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert result['auto_retry_authorized'] is False


def test_capsule_unknown_outcome_must_not_be_retried(monkeypatch):
    monkeypatch.setattr(live, '_CAPSULE_LIVE_PATCH_ENABLED', True)
    calls = []
    before = SimpleNamespace(metadata=_metadata(), spec={})

    class _Core:
        def read_namespace(self, **kwargs):
            calls.append('read')
            return before
        def patch_namespace(self, **kwargs):
            calls.append('patch')
            if kwargs.get('dry_run') == 'All':
                return before
            raise TimeoutError('provider outcome unknown')

    monkeypatch.setattr(
        live, 'capture_capsule_namespace_baseline', lambda *a, **k: {},
    )
    monkeypatch.setattr(
        live, 'build_capsule_namespace_handoff_patch',
        lambda *a, **k: [{'op': 'test', 'path': '/metadata/uid', 'value': 'provider-uid'}],
    )
    monkeypatch.setattr(live, 'verify_capsule_namespace_preview', lambda **_: None)
    monkeypatch.setattr(live, 'capsule_preservation_digest', lambda obj: obj.spec)
    with pytest.raises(TimeoutError, match='outcome unknown'):
        live.execute_capsule_single_metadata_patch_staged(
            core=_Core(), rbac=SimpleNamespace(), component=_component(),
            tenant_id='tenant-1', capsule_name='demo',
            capsule_uid='cr-uid', successor_owner='platform-team',
        )
    assert calls == ['read', 'patch', 'read', 'patch']
