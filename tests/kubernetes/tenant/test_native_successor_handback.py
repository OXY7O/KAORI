"""#1049 provider preservation and exact Released handback admission."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.discovery_adoption import _require_re_adoption_handback_for_managed_release
from app.kubernetes.tenant.native_handoff_dry_run import (
    _retained_provider_metadata, _spec, _stable_sha256,
)
from app.kubernetes.tenant.native_successor_handback import (
    _validate_released_component, handback_native_successor_governance_committed,
)


def resource(*, manager='platform-team'):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='dev', uid='namespace-uid', resource_version='45',
            labels={
                'app.kubernetes.io/managed-by': manager,
                'example.com/retained': 'yes',
            },
            annotations={'example.com/audit': 'preserved'},
            owner_references=[], finalizers=['protect'], generation=1,
            deletion_timestamp=None, deletion_grace_period_seconds=None,
        ),
        spec={'hard': {'requests.cpu': '8', 'requests.memory': '16Gi'}},
    )


def preview():
    source = resource()
    return {
        'name': 'dev', 'uid': 'namespace-uid', 'kind': 'Namespace',
        'namespace': 'dev',
        'spec_sha256': _stable_sha256(_spec(source)),
        'retained_metadata_sha256': _stable_sha256(_retained_provider_metadata(source)),
    }


def test_handback_requires_exact_successor_marker_and_unchanged_provider_spec():
    _validate_released_component(
        item=preview(), live=resource(), successor_owner='platform-team',
    )
    mismatch = deepcopy(resource())
    mismatch.spec['hard']['requests.cpu'] = '16'
    with pytest.raises(ValueError, match='no longer owned'):
        _validate_released_component(
            item=preview(), live=mismatch, successor_owner='platform-team',
        )
    with pytest.raises(ValueError, match='no longer owned'):
        _validate_released_component(
            item=preview(), live=resource(manager='someone-else'),
            successor_owner='platform-team',
        )


def test_handback_requires_explicit_confirmation():
    with pytest.raises(ValueError, match='explicitly authorize'):
        handback_native_successor_governance_committed(
            tenant_id='tenant-a', actor_user_id=52,
            release_plan_sha256='a' * 64,
            provider_token='transient', confirmed=False,
        )


def test_existing_observation_only_re_adopt_still_does_not_require_handback():
    _require_re_adoption_handback_for_managed_release(
        provider_evidence={'provider_mutation_performed': False},
        release_evidence={'status': 'released', 'provider_mutation_performed': False},
    )


def test_managed_re_adopt_requires_verified_exact_uid_and_resource_version():
    evidence = {
        'provider_mutation_performed': True,
        'handback_governance': {
            'status': 'verified', 'release_plan_sha256': 'a' * 64,
            'provider_uid': 'namespace-uid', 'resource_version': '47',
            'successor_owner': 'platform-team',
        },
    }
    release = {
        'status': 'released', 'release_mode': 'managed_handoff',
        'plan_sha256': 'a' * 64, 'successor_owner': 'platform-team',
        'provider_handoff_verified': True,
    }
    _require_re_adoption_handback_for_managed_release(
        provider_evidence=evidence, release_evidence=release,
        provider_uid='namespace-uid', resource_version='47',
    )
    with pytest.raises(ValueError, match='verified successor handback'):
        _require_re_adoption_handback_for_managed_release(
            provider_evidence=evidence, release_evidence=release,
            provider_uid='namespace-uid', resource_version='48',
        )
    with pytest.raises(ValueError, match='verified successor handback'):
        _require_re_adoption_handback_for_managed_release(
            provider_evidence=evidence, release_evidence=release,
            provider_uid='replaced', resource_version='47',
        )


def test_released_tenant_handback_uses_namespace_version_ledger():
    evidence = {
        'provider_mutation_performed': True,
        'handback_governance': {
            'status': 'verified', 'release_plan_sha256': 'a' * 64,
            'provider_uid': 'namespace-uid',
            'provider_resource_versions': {'dev': '47'},
            'successor_owner': 'platform-team',
        },
    }
    release = {
        'status': 'released', 'release_mode': 'managed_handoff',
        'plan_sha256': 'a' * 64, 'successor_owner': 'platform-team',
        'provider_handoff_verified': True,
    }
    _require_re_adoption_handback_for_managed_release(
        provider_evidence=evidence, release_evidence=release,
        provider_uid='namespace-uid', resource_version='47', namespace='dev',
    )
    with pytest.raises(ValueError, match='verified successor handback'):
        _require_re_adoption_handback_for_managed_release(
            provider_evidence=evidence, release_evidence=release,
            provider_uid='namespace-uid', resource_version='47', namespace='other',
        )


def test_handback_never_reuses_release_forced_adoption_or_modifies_specs():
    from pathlib import Path
    source = (
        Path(__file__).resolve().parents[3]
        / 'app/kubernetes/tenant/native_successor_handback.py'
    ).read_text(encoding='utf-8')
    assert 'verify_native_successor_resource_authority(' in source
    assert "ownership_required='external_successor_correlated'" in source
    assert "TenantLifecycleStatus.RELEASED.value" in source
    assert "'adoption_automatic': False" in source
    assert "'release_plan_sha256'" in source
    assert "'op': 'remove'" in source
    assert "with_for_update()" in source
    for forbidden in (
        "delete_namespace(", "delete_namespaced_resource_quota(",
        "create_namespace(", "release_verified_native_tenant_committed(",
    ):
        assert forbidden not in source
