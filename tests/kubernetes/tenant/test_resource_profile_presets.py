from types import SimpleNamespace

from app.kubernetes.tenant.service import RESOURCE_PROFILE_PRESETS, _namespace_allocation_values, _profile_values


def test_standard_preset_exposes_approved_initial_values() -> None:
    standard = RESOURCE_PROFILE_PRESETS['standard']

    assert standard['quota']['requests.cpu'] == '2'
    assert standard['quota']['requests.memory'] == '4Gi'
    assert standard['limits']['default']['cpu'] == '500m'
    assert standard['limits']['default_request']['memory'] == '128Mi'


def test_submitted_values_remain_authoritative_after_preset_fill() -> None:
    quota, limits = _profile_values(
        {
            'requests_cpu': '3',
            'limits_cpu': '',
            'requests_memory': '',
            'limits_memory': '',
            'pods': '',
            'persistentvolumeclaims': '',
            'requests_storage': '',
            'services': '',
            'configmaps': '',
            'secrets': '',
            'default_cpu': '',
            'default_memory': '',
            'default_request_cpu': '',
            'default_request_memory': '',
        }
    )

    assert quota == {'requests.cpu': '3'}
    assert limits == {}


def test_blank_profile_dimensions_are_explicitly_unbounded() -> None:
    quota, limits = _profile_values({})

    assert quota == {}
    assert limits == {}


def test_namespace_allocation_detects_profile_override() -> None:
    profile = SimpleNamespace(
        quota_hard_json={'requests.cpu': '2', 'requests.memory': '4Gi'},
        limit_defaults_json={'default': {'cpu': '500m'}},
    )

    quota, limits, customized = _namespace_allocation_values(
        profile,
        {
            'requests_cpu': '3',
            'requests_memory': '4Gi',
            'default_cpu': '500m',
        },
    )

    assert quota == {'requests.cpu': '3', 'requests.memory': '4Gi'}
    assert limits == {'default': {'cpu': '500m'}}
    assert customized is True


def test_namespace_allocation_uses_profile_snapshot_when_fields_are_absent() -> None:
    profile = SimpleNamespace(
        quota_hard_json={'requests.cpu': '2'},
        limit_defaults_json={},
    )

    quota, limits, customized = _namespace_allocation_values(profile, {})

    assert quota == {'requests.cpu': '2'}
    assert limits == {}
    assert customized is False
