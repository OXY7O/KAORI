from types import SimpleNamespace

from app.kubernetes.tenant.service import (
    RESOURCE_PROFILE_PRESETS,
    _namespace_allocation_values,
    _profile_values,
    _resource_profile_values,
)


def test_standard_preset_exposes_canonical_versioned_values() -> None:
    standard = RESOURCE_PROFILE_PRESETS['standard']

    assert standard['version'] == 1
    assert standard['quota']['requests.cpu'] == '2'
    assert standard['quota']['requests.memory'] == '4Gi'
    assert standard['limits']['default']['cpu'] == '500m'
    assert standard['limits']['default_request']['memory'] == '128Mi'


def test_builtin_preset_ignores_submitted_resource_overrides() -> None:
    quota, limits, version, base_class, base_version = _resource_profile_values(
        'standard',
        {
            'requests_cpu': '99',
            'requests_memory': '99Gi',
            'default_cpu': '99',
        },
    )

    assert quota == RESOURCE_PROFILE_PRESETS['standard']['quota']
    assert limits == RESOURCE_PROFILE_PRESETS['standard']['limits']
    assert version == RESOURCE_PROFILE_PRESETS['standard']['version']
    assert base_class is None
    assert base_version is None


def test_custom_profile_accepts_values_and_preserves_base_preset_lineage() -> None:
    quota, limits, version, base_class, base_version = _resource_profile_values(
        'custom',
        {
            'base_preset_class': 'standard',
            'requests_cpu': '3',
            'requests_memory': '6Gi',
            'default_cpu': '750m',
        },
    )

    assert quota == {'requests.cpu': '3', 'requests.memory': '6Gi'}
    assert limits == {'default': {'cpu': '750m'}}
    assert version == 1
    assert base_class == 'standard'
    assert base_version == RESOURCE_PROFILE_PRESETS['standard']['version']


def test_blank_custom_profile_dimensions_are_explicitly_unbounded() -> None:
    quota, limits = _profile_values({})

    assert quota == {}
    assert limits == {}


def test_namespace_allocation_uses_canonical_builtin_snapshot() -> None:
    profile = SimpleNamespace(
        profile_class='standard',
        quota_hard_json={'requests.cpu': '99'},
        limit_defaults_json={'default': {'cpu': '99'}},
    )

    quota, limits, customized = _namespace_allocation_values(profile)

    assert quota == RESOURCE_PROFILE_PRESETS['standard']['quota']
    assert limits == RESOURCE_PROFILE_PRESETS['standard']['limits']
    assert customized is False


def test_namespace_allocation_uses_committed_custom_profile_snapshot() -> None:
    profile = SimpleNamespace(
        profile_class='custom',
        quota_hard_json={'requests.cpu': '3'},
        limit_defaults_json={'default': {'cpu': '750m'}},
    )

    quota, limits, customized = _namespace_allocation_values(profile)

    assert quota == {'requests.cpu': '3'}
    assert limits == {'default': {'cpu': '750m'}}
    assert customized is True
