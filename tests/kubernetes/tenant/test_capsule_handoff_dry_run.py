"""#1229 Capsule server dryRun=All: no live execution and no false readiness."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_dry_run import (
    preview_capsule_handoff_scope,
    preview_capsule_namespace_handoff,
)
from app.kubernetes.tenant.release_handoff_inventory import _capsule_spec_sha256


def _namespace():
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='demo-dev', uid='ns-uid', resource_version='11',
            labels={
                'app.kubernetes.io/managed-by': 'kaori',
                'kaori.io/tenant-id': 'tenant-uuid',
                'capsule.clastix.io/tenant': 'demo',
                'foreign.example/keep': 'yes',
            },
            annotations={'foreign.example/annotation': 'preserved'},
            owner_references=[{'kind': 'Tenant', 'name': 'demo'}],
            finalizers=['capsule.clastix.io/protect'],
            generation=1, deletion_timestamp=None,
            deletion_grace_period_seconds=None,
        ),
        spec={'finalizers': ['kubernetes']},
    )


def _components():
    return [
        {
            'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid',
            'resource_version': '5', 'authority': 'capsule',
            'handoff': 'external_acceptance_required',
            'ownership': 'external_or_unattributed',
            'capsule_spec_sha256': _capsule_spec_sha256({'resourceQuotas': {'scope': 'Tenant'}}),
        },
        {
            'kind': 'Namespace', 'name': 'demo-dev', 'namespace': 'demo-dev',
            'uid': 'ns-uid', 'resource_version': '11', 'authority': 'capsule',
            'handoff': 'external_acceptance_required', 'ownership': 'kaori_marker_correlated',
        },
    ]


class _Core:
    def __init__(self, *, corrupt=False):
        self.calls = []
        self.corrupt = corrupt

    def read_namespace(self, name, **kwargs):
        self.calls.append(('read', name, kwargs))
        return _namespace()

    def patch_namespace(self, **kwargs):
        self.calls.append(('patch', kwargs))
        assert kwargs['dry_run'] == 'All'
        assert kwargs['_content_type'] == 'application/json-patch+json'
        preview = deepcopy(_namespace())
        preview.metadata.labels['app.kubernetes.io/managed-by'] = 'platform-team'
        del preview.metadata.labels['kaori.io/tenant-id']
        if self.corrupt:
            preview.metadata.finalizers = []
        return preview


class _Custom:
    def __init__(self):
        self.calls = []

    def get_cluster_custom_object(self, group, version, plural, name, **kwargs):
        self.calls.append((group, version, plural, name, kwargs))
        return {
            'metadata': {
                'name': 'demo', 'uid': 'cr-uid',
                'resourceVersion': '5',
                'labels': {'capsule.clastix.io/policy': 'preserved'},
            },
            'spec': {'resourceQuotas': {'scope': 'Tenant'}},
        }


def test_preview_uses_server_dry_run_only_and_rechecks_provider():
    core, custom = _Core(), _Custom()
    receipt = preview_capsule_handoff_scope(
        custom=custom, core=core, components=_components(),
        tenant_id='tenant-uuid', successor_owner='platform-team',
    )
    assert [call[0] for call in core.calls] == ['read', 'patch', 'read']
    assert len(custom.calls) == 2
    assert all(call[1] == 'v1beta2' for call in custom.calls)
    assert receipt['status'] == 'preview_observed_coverage_incomplete'
    assert receipt['dry_run_complete'] is False
    assert receipt['quota_limit_rbac_inventory_verified'] is False
    assert receipt['provider_mutation_performed'] is False
    assert receipt['provider_handoff_verified'] is False
    assert receipt['release_authorized'] is False


def test_observed_capsule_namespace_preserves_foreign_manager_without_patch():
    component = {
        **_components()[1],
        'handoff': 'observe_only',
        'ownership': 'external_or_unattributed',
        'managed_by': 'capsule',
    }

    class _ObservedCore:
        def __init__(self):
            self.calls = []

        def read_namespace(self, name, **kwargs):
            self.calls.append(('read', name))
            resource = _namespace()
            resource.metadata.labels.pop('kaori.io/tenant-id')
            resource.metadata.labels['app.kubernetes.io/managed-by'] = 'capsule'
            return resource

        def patch_namespace(self, **kwargs):
            pytest.fail('Observed Capsule Namespace must NEVER be PATCHed')

    core = _ObservedCore()
    result = preview_capsule_namespace_handoff(
        core, component, tenant_id='tenant-uuid',
        capsule_tenant_name='demo', successor_owner='platform-team',
    )
    assert result['operation'] == 'observe_capsule_namespace_without_transfer'
    assert result['dry_run'] is False
    assert result['live_provider_unchanged'] is True
    assert [call[0] for call in core.calls] == ['read', 'read']

    full = preview_capsule_handoff_scope(
        custom=_Custom(), core=_ObservedCore(),
        components=[_components()[0], component],
        tenant_id='tenant-uuid', successor_owner='platform-team',
    )
    assert full['status'] == 'preview_observed_coverage_incomplete'
    assert full['namespace_count'] == 1
    assert full['namespace_preview_count'] == 0
    assert full['dry_run_complete'] is False
    assert full['provider_handoff_verified'] is False
    assert full['release_authorized'] is False


def test_observed_capsule_namespace_blocks_unknown_kaori_control_label():
    component = {
        **_components()[1], 'handoff': 'observe_only',
        'ownership': 'external_or_unattributed', 'managed_by': '',
    }

    class _OrphanMarkerCore:
        def read_namespace(self, name, **kwargs):
            resource = _namespace()
            resource.metadata.labels.pop('kaori.io/tenant-id')
            resource.metadata.labels.pop('app.kubernetes.io/managed-by')
            resource.metadata.labels['kaori.io/unknown-control'] = 'unverified'
            return resource

        def patch_namespace(self, **kwargs):
            pytest.fail('Unclassified KAORI label must block any PATCH')

    with pytest.raises(ValueError, match='unclassified KAORI control labels'):
        preview_capsule_namespace_handoff(
            _OrphanMarkerCore(), component, tenant_id='tenant-uuid',
            capsule_tenant_name='demo', successor_owner='platform-team',
        )


def test_observed_capsule_namespace_rejects_changed_manager():
    component = {
        **_components()[1], 'handoff': 'observe_only',
        'ownership': 'external_or_unattributed', 'managed_by': '',
    }
    class _ForeignManagerCore:
        def read_namespace(self, name, **kwargs):
            resource = _namespace()
            resource.metadata.labels.pop('kaori.io/tenant-id')
            resource.metadata.labels['app.kubernetes.io/managed-by'] = 'capsule'
            return resource
        def patch_namespace(self, **kwargs):
            pytest.fail('Stale observed manager must not be patched')

    with pytest.raises(ValueError, match='manager changed'):
        preview_capsule_namespace_handoff(
            _ForeignManagerCore(), component, tenant_id='tenant-uuid',
            capsule_tenant_name='demo', successor_owner='platform-team',
        )


def test_preview_rejects_admission_that_mutates_finalizers():
    with pytest.raises(ValueError, match='provider-owned'):
        preview_capsule_namespace_handoff(
            _Core(corrupt=True), _components()[1],
            tenant_id='tenant-uuid', capsule_tenant_name='demo',
            successor_owner='platform-team',
        )


def test_preview_rejects_foreign_cr_drift_or_unsupported_scope_without_patching():
    components = _components()
    components[0]['capsule_spec_sha256'] = 'b' * 64
    core = _Core()
    with pytest.raises(ValueError, match='spec'):
        preview_capsule_handoff_scope(
            custom=_Custom(), core=core, components=components,
            tenant_id='tenant-uuid', successor_owner='platform-team',
        )
    assert not core.calls
    components = _components()
    components[1]['kind'] = 'RoleBinding'
    with pytest.raises(ValueError):
        preview_capsule_handoff_scope(
            custom=_Custom(), core=core, components=components,
            tenant_id='tenant-uuid', successor_owner='platform-team',
        )
    assert not core.calls
