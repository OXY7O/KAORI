from app.kubernetes.tenant.service import RESOURCE_PROFILE_PRESETS, profile_values


def test_small_standard_and_large_profiles_ignore_submitted_override_values() -> None:
    source = {
        'requests_cpu': '999',
        'limits_cpu': '999',
        'requests_memory': '999Gi',
        'limits_memory': '999Gi',
        'pods': '999',
        'default_request_cpu': '999',
        'default_cpu': '999',
        'default_request_memory': '999Gi',
        'default_memory': '999Gi',
    }

    for profile_class in ('small', 'standard', 'large'):
        quota, limits = profile_values(profile_class, source)
        assert quota == RESOURCE_PROFILE_PRESETS[profile_class]['quota']
        assert limits == RESOURCE_PROFILE_PRESETS[profile_class]['limits']


def test_custom_profile_uses_operator_values() -> None:
    quota, limits = profile_values(
        'custom',
        {
            'requests_cpu': '3',
            'pods': '12',
            'default_request_cpu': '150m',
            'default_cpu': '750m',
        },
    )

    assert quota == {'requests.cpu': '3', 'pods': '12'}
    assert limits == {
        'default_request': {'cpu': '150m'},
        'default': {'cpu': '750m'},
    }
