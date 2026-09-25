import pytest

from app.kubernetes.tenant.validation import validate_namespace_name, validate_profile_spec


def test_namespace_name_uses_dns_label_contract() -> None:
    assert validate_namespace_name('payments-prod') == 'payments-prod'
    for value in ('Payments', '-payments', 'payments_', 'a' * 64):
        with pytest.raises(ValueError):
            validate_namespace_name(value)


def test_resource_profile_rejects_unsupported_and_unsafe_quota_values() -> None:
    quota, limits = validate_profile_spec(
        {
            'requests.cpu': '2',
            'limits.cpu': '4',
            'requests.memory': '4Gi',
            'limits.memory': '8Gi',
            'pods': '20',
            'persistentvolumeclaims': '10',
            'requests.storage': '100Gi',
            'services': '10',
            'configmaps': '50',
            'secrets': '50',
        },
        {
            'default': {'cpu': '500m', 'memory': '512Mi'},
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
        },
    )
    assert quota['requests.storage'] == '100Gi'
    assert limits['default_request']['cpu'] == '100m'

    with pytest.raises(ValueError, match='unsupported quota'):
        validate_profile_spec({'requests.nvidia.com/gpu': '1'})
    with pytest.raises(ValueError, match='positive integer'):
        validate_profile_spec({'pods': '0'})
