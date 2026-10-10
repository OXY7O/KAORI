from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_handoff_dry_run import (
    _retained_provider_metadata, _spec, _stable_sha256,
)
from app.kubernetes.tenant.native_handoff_readback import verify_external_native_component


def _resource(*, manager='kaori', uid='uid-1', rv='21'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='dev', uid=uid, resource_version=rv,
            labels={
                'app.kubernetes.io/managed-by': manager,
                'example.com/retained': 'yes',
            },
            annotations={'example.com/audit': 'preserved'},
            owner_references=[], finalizers=['example.com/keep'],
            generation=1, deletion_timestamp=None, deletion_grace_period_seconds=None,
        ),
        spec={'hard': {'requests.cpu': '2'}},
    )


def _receipt(before):
    return {
        'kind': 'ResourceQuota', 'name': 'dev', 'uid': 'uid-1',
        'resource_version': '21', 'operation': 'metadata_only_json_patch_dry_run',
        'spec_sha256': _stable_sha256(_spec(before)),
        'retained_metadata_sha256': _stable_sha256(_retained_provider_metadata(before)),
    }


def test_native_external_handoff_receipt_proves_only_matching_provider_state():
    baseline = _resource()
    # Real provisioning label must be excluded from retained foreign metadata.
    baseline.metadata.labels['kaori.io/resource-profile'] = 'profile-v4'
    transferred = _resource(manager='platform-team', rv='22')
    output = verify_external_native_component(
        before=_receipt(baseline), current=transferred, successor_owner='platform-team'
    )
    assert output['spec_preserved'] is True
    assert output['foreign_metadata_preserved'] is True
    assert output['provider_mutation_performed_by_kaori'] is False


@pytest.mark.parametrize('change', [
    lambda obj: setattr(obj.metadata, 'uid', 'different'),
    lambda obj: setattr(obj.metadata, 'resource_version', '21'),
    lambda obj: obj.metadata.labels.update({'kaori.io/tenant-id': 'tenant-a'}),
    lambda obj: obj.metadata.labels.update({'kaori.io/resource-profile': 'profile-v4'}),
    lambda obj: obj.metadata.labels.update({'kaori.io/tenant-generation': '4'}),
    lambda obj: obj.metadata.labels.update({'app.kubernetes.io/managed-by': 'unknown'}),
    lambda obj: obj.metadata.annotations.update({'foreign': 'unexpected'}),
    lambda obj: obj.metadata.labels.update({'example.com/retained': 'modified'}),
    lambda obj: setattr(obj.metadata, 'finalizers', []),
    lambda obj: setattr(obj, 'spec', {'hard': {'requests.cpu': '4'}}),
])
def test_native_readback_rejects_partial_ambiguous_or_spec_drift(change):
    baseline = _resource()
    provider = deepcopy(_resource(manager='platform-team', rv='22'))
    change(provider)
    with pytest.raises(ValueError):
        verify_external_native_component(
            before=_receipt(baseline), current=provider, successor_owner='platform-team'
        )


def test_native_readback_rejects_receipt_without_dryrun_integrity():
    baseline = _resource()
    receipt = _receipt(baseline)
    receipt['operation'] = 'unapproved_transfer'
    with pytest.raises(ValueError, match='dry-run'):
        verify_external_native_component(
            before=receipt, current=_resource(manager='platform-team', rv='22'),
            successor_owner='platform-team'
        )
