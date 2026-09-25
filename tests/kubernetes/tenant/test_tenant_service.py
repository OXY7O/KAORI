import pytest

from app.kubernetes.tenant.resource_profiles import preset_form_values, resolve_resource_profile_spec
from app.kubernetes.tenant.service import normalize_tenant_slug


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ('Payments', 'payments'),
        ('Payments Platform', 'payments-platform'),
        ('payments_core', 'payments-core'),
    ],
)
def test_normalize_tenant_slug(source: str, expected: str) -> None:
    assert normalize_tenant_slug(source) == expected


def test_normalize_tenant_slug_rejects_empty_or_overlong_values() -> None:
    with pytest.raises(ValueError):
        normalize_tenant_slug('---')
    with pytest.raises(ValueError):
        normalize_tenant_slug('a' * 64)


def test_standard_resource_profile_preset_is_canonical() -> None:
    quota, limits = resolve_resource_profile_spec('standard')

    assert quota['requests.cpu'] == '2'
    assert quota['limits.memory'] == '8Gi'
    assert quota['pods'] == '20'
    assert quota['requests.storage'] == '100Gi'
    assert limits['default_request']['cpu'] == '100m'
    assert limits['default']['memory'] == '512Mi'


def test_preset_form_values_match_server_contract() -> None:
    payload = preset_form_values()

    assert set(payload) == {'small', 'standard', 'large'}
    assert payload['small']['values']['pods'] == '10'
    assert payload['standard']['values']['requests_memory'] == '4Gi'
    assert payload['large']['values']['default_cpu'] == '1000m'


def test_unknown_resource_profile_preset_fails_closed() -> None:
    with pytest.raises(ValueError, match='does not have a KAORI preset'):
        resolve_resource_profile_spec('custom')
