import pytest

from app.kubernetes.tenant.service import RESOURCE_PROFILE_PRESETS, normalize_tenant_slug


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


def test_resource_profile_presets_have_canonical_native_defaults() -> None:
    assert set(RESOURCE_PROFILE_PRESETS) == {'small', 'standard', 'large'}
    assert RESOURCE_PROFILE_PRESETS['small']['quota_hard']['requests.cpu'] == '1'
    assert RESOURCE_PROFILE_PRESETS['standard']['quota_hard']['requests.memory'] == '4Gi'
    assert RESOURCE_PROFILE_PRESETS['large']['quota_hard']['requests.storage'] == '200Gi'
    assert RESOURCE_PROFILE_PRESETS['standard']['limit_defaults']['default']['cpu'] == '500m'
