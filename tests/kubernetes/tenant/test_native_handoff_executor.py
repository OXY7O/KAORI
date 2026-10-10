"""Native handoff executor negative and provider-mocked preservation boundaries."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_executor import (
    _approved_component_for_preview, _patch_native_live,
    _verify_patch_preview, execute_native_handoff_committed,
)
from app.kubernetes.tenant.native_handoff_transfer_patch import (
    build_native_successor_handoff_patch,
)


def resource(*, kind='Namespace', manager='kaori'):
    labels = {
        'app.kubernetes.io/managed-by': manager,
        'example.com/keep': 'untouched',
    }
    if manager == 'kaori':
        labels.update({
            'kaori.io/tenant-id': 'tenant-a',
            'kaori.io/environment': 'development',
            'kaori.io/resource-profile': 'profile-uuid-v2',
            'kaori.io/tenant-generation': '2',
            'kaori.io/profile-id': 'v2',
        })
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='dev', uid='provider-uid', resource_version='21',
            labels=labels, annotations={'example.com/note': 'keep'},
            owner_references=[], finalizers=['example.com/protect'],
            generation=1, deletion_timestamp=None,
            deletion_grace_period_seconds=None,
        ),
        spec=None if kind == 'Namespace' else {'hard': {'requests.cpu': '8'}},
    )


class FakeCore:
    def __init__(self):
        self.calls = []

    def patch_namespace(self, **kwargs):
        self.calls.append(('Namespace', kwargs))

    def patch_namespaced_resource_quota(self, **kwargs):
        self.calls.append(('ResourceQuota', kwargs))

    def patch_namespaced_limit_range(self, **kwargs):
        self.calls.append(('LimitRange', kwargs))


def _approved_plan_component(kind='ResourceQuota'):
    return {
        'namespace': 'dev', 'kind': kind, 'name': 'dev',
        'uid': 'provider-uid', 'resource_version': '21',
        'handoff': 'external_acceptance_required',
        'ownership': 'kaori_marker_correlated',
    }


def _canonical_preview(kind='ResourceQuota'):
    # Exact evidence shape produced by dry_run_native_handoff_component:
    # it intentionally does not contain handoff or ownership.
    return {
        'namespace': 'dev', 'kind': kind, 'name': 'dev',
        'uid': 'provider-uid', 'resource_version': '21',
        'operation': 'metadata_only_json_patch_dry_run',
        'dry_run': True, 'live_provider_unchanged': True,
        'spec_unchanged': True, 'spec_sha256': 'abc',
        'retained_metadata_sha256': 'def',
        'label_keys_to_release': [
            'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
            'kaori.io/environment', 'kaori.io/resource-profile',
            'kaori.io/tenant-generation', 'kaori.io/profile-id',
        ],
    }


@pytest.mark.parametrize('kind', ['Namespace', 'ResourceQuota', 'LimitRange'])
def test_live_patch_resolves_approved_scope_from_real_preview_shape(kind):
    approved = _approved_plan_component(kind)
    preview = _canonical_preview(kind)
    assert 'handoff' not in preview and 'ownership' not in preview
    resolved = _approved_component_for_preview(
        plan={'handoff_components': [approved]}, preview=preview,
    )
    assert resolved is approved
    ops = build_native_successor_handoff_patch(
        resolved, resource(kind=kind), tenant_id='tenant-a',
        verified_successor_owner='platform-team',
    )
    assert ops[:2] == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'provider-uid'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '21'},
    ]
    assert ops[-1] == {
        'op': 'add', 'path': '/metadata/labels/app.kubernetes.io~1managed-by',
        'value': 'platform-team',
    }
    assert all(op['path'].startswith('/metadata/') for op in ops)
    assert not any('spec' in op['path'] for op in ops)
    assert 'handoff' not in preview and 'ownership' not in preview


@pytest.mark.parametrize('field,value', [
    ('resource_version', '22'),
    ('uid', 'different-uid'),
    ('kind', 'LimitRange'),
    ('name', 'other-resource'),
    ('operation', 'other-operation'),
    ('dry_run', False),
    ('live_provider_unchanged', False),
])
def test_live_patch_rejects_incomplete_or_changed_preview_scope(field, value):
    preview = _canonical_preview()
    preview[field] = value
    with pytest.raises(ValueError):
        _approved_component_for_preview(
            plan={'handoff_components': [_approved_plan_component()]},
            preview=preview,
        )


@pytest.mark.parametrize('field,value', [
    ('handoff', 'observe_only'),
    ('ownership', 'provider_owned'),
    ('resource_version', '22'),
])
def test_live_patch_rejects_unapproved_authority_or_stale_rv(field, value):
    approved = _approved_plan_component()
    approved[field] = value
    with pytest.raises(ValueError):
        _approved_component_for_preview(
            plan={'handoff_components': [approved]},
            preview=_canonical_preview(),
        )


def test_live_patch_rejects_duplicate_approved_identity():
    component = _approved_plan_component()
    with pytest.raises(ValueError, match='uniquely bound'):
        _approved_component_for_preview(
            plan={'handoff_components': [component, dict(component)]},
            preview=_canonical_preview(),
        )


@pytest.mark.parametrize('kind', ['Namespace', 'ResourceQuota', 'LimitRange'])
def test_executor_dispatches_only_json_patch_without_dry_run_or_spec(kind):
    core = FakeCore()
    component = {'kind': kind, 'name': 'dev', 'namespace': 'dev'}
    patch = [
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '21'},
        {'op': 'add', 'path': '/metadata/labels/app.kubernetes.io~1managed-by', 'value': 'platform-team'},
    ]
    _patch_native_live(core, component, patch)
    assert len(core.calls) == 1
    assert core.calls[0][0] == kind
    kwargs = core.calls[0][1]
    assert kwargs['body'] == patch
    assert kwargs['_content_type'] == 'application/json-patch+json'
    assert kwargs['_request_timeout'] == 5
    assert 'dry_run' not in kwargs


def test_executor_admission_preview_preserves_resource_values_and_foreign_metadata():
    before = resource(kind='ResourceQuota')
    after = resource(kind='ResourceQuota', manager='platform-team')
    _verify_patch_preview(
        before=before, preview=after, successor_owner='platform-team',
    )
    altered = deepcopy(after)
    altered.spec['hard']['requests.cpu'] = '24'
    with pytest.raises(ValueError, match='nonownership'):
        _verify_patch_preview(
            before=before, preview=altered, successor_owner='platform-team',
        )
    altered = deepcopy(after)
    altered.metadata.labels['example.com/keep'] = 'tampered'
    with pytest.raises(ValueError, match='nonownership'):
        _verify_patch_preview(
            before=before, preview=altered, successor_owner='platform-team',
        )


def test_executor_never_calls_provider_without_explicit_mutation_confirmation():
    with pytest.raises(ValueError, match='Explicit'):
        execute_native_handoff_committed(
            tenant_id='tenant-a', actor_user_id=31,
            plan_sha256='a' * 64, confirmed=False,
        )


def test_no_full_transfer_or_release_in_unadmitted_evidence():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3]
        / 'app/kubernetes/tenant/native_handoff_executor.py'
    ).read_text(encoding='utf-8')
    assert "'status': 'in_progress'" in source
    assert "partial_handoff_recovery_required" in source
    assert "'release_authorized': False" in source
    assert "verify_native_provider_admin_authority(" in source
    assert "require_platform_admin_actor(" in source
    assert "require_current_native_acceptance(" in source
    assert "verify_external_native_component(" in source
    assert "with_for_update()" in source
    assert "delete_namespace(" not in source
    assert "delete_namespaced_resource_quota(" not in source
    assert "release_adopted_tenant_committed(" not in source


def test_x509_platform_admin_authority_is_not_a_separate_successor_token():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    executor = (root / 'app/kubernetes/tenant/native_handoff_executor.py').read_text()
    route = (root / 'app/kubernetes/tenant/routes.py').read_text()
    view = (root / 'app/templates/kubernetes/tenant/partials/_tenant_registry.html').read_text()
    assert "provider_token" not in executor
    assert "provider_token" not in route
    assert "kubernetes_successor_token" not in view or 'Successor Handback' in view
    assert "verified_provider_identity" in (
        root / 'app/kubernetes/tenant/native_successor_acceptance.py'
    ).read_text()
    assert "@permission_required('clusters.manage')" in route
