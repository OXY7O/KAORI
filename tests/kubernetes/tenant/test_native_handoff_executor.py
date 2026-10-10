"""Native handoff executor negative and provider-mocked preservation boundaries."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_executor import (
    _patch_native_live, _verify_patch_preview, execute_native_handoff_committed,
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
            plan_sha256='a' * 64, provider_token='token',
            confirmed=False,
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
    assert "verify_native_successor_resource_authority(" in source
    assert "require_current_native_acceptance(" in source
    assert "verify_external_native_component(" in source
    assert "with_for_update()" in source
    assert "delete_namespace(" not in source
    assert "delete_namespaced_resource_quota(" not in source
    assert "release_adopted_tenant_committed(" not in source
