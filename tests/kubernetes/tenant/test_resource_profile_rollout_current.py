"""Committed Resource Profile rollout no-op comparison (#2381)."""

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.resource_profile_controls import (
    namespace_allocation_is_current,
    namespace_allocation_values,
)
from app.kubernetes.tenant.service_contracts import RESOURCE_PROFILE_PRESETS


def profile_and_snapshot():
    profile = SimpleNamespace(
        profile_class='custom',
        version=2,
        quota_hard_json={'requests.cpu': '2'},
        limit_defaults_json={'default': {'cpu': '500m'}},
        storage_policy_json={'min': '1Gi', 'max': '10Gi'},
    )
    quota, limits, storage, _ = namespace_allocation_values(profile)
    record = SimpleNamespace(
        resource_profile_version=2,
        allocation_quota_json=quota,
        allocation_limit_defaults_json=limits,
        allocation_storage_policy_json=storage,
    )
    return profile, record, quota, limits, storage


def test_matching_version_quota_defaults_and_storage_is_current() -> None:
    profile, record, quota, limits, storage = profile_and_snapshot()

    assert namespace_allocation_is_current(record, profile, quota, limits, storage)


@pytest.mark.parametrize('mismatch', ['version', 'quota', 'limits', 'storage'])
def test_every_allocation_mismatch_remains_rollout_pending(mismatch: str) -> None:
    profile, record, quota, limits, storage = profile_and_snapshot()
    if mismatch == 'version':
        record.resource_profile_version = 1
    elif mismatch == 'quota':
        record.allocation_quota_json = {'requests.cpu': '3'}
    elif mismatch == 'limits':
        record.allocation_limit_defaults_json = {'default': {'cpu': '750m'}}
    elif mismatch == 'storage':
        record.allocation_storage_policy_json = {'min': '2Gi', 'max': '10Gi'}

    assert not namespace_allocation_is_current(record, profile, quota, limits, storage)


def test_unknown_snapshot_is_not_assumed_current() -> None:
    profile, record, quota, limits, storage = profile_and_snapshot()
    record.resource_profile_version = None
    record.allocation_storage_policy_json = None
    assert not namespace_allocation_is_current(record, profile, quota, limits, storage)


def test_builtin_profile_comparison_uses_canonical_preset_not_stale_saved_value() -> None:
    profile = SimpleNamespace(
        profile_class='small',
        version=2,
        quota_hard_json={'requests.cpu': '99'},
        limit_defaults_json={'default': {'cpu': '99'}},
        storage_policy_json={'min': '1Gi', 'max': '10Gi'},
    )
    quota, limits, storage, customized = namespace_allocation_values(profile)
    assert not customized
    assert quota == {'requests.cpu': RESOURCE_PROFILE_PRESETS['small']['quota']['requests.cpu']}
    assert limits == {'default': {'cpu': RESOURCE_PROFILE_PRESETS['small']['limits']['default']['cpu']}}

    record = SimpleNamespace(
        resource_profile_version=2,
        allocation_quota_json=quota,
        allocation_limit_defaults_json=limits,
        allocation_storage_policy_json=storage,
    )
    assert namespace_allocation_is_current(record, profile, quota, limits, storage)
    record.allocation_quota_json = {'requests.cpu': '99'}
    assert not namespace_allocation_is_current(record, profile, quota, limits, storage)
