from __future__ import annotations

import pytest

from app.kubernetes.tenant.discovery_adoption import validate_adoption_provider_identity


def test_native_and_capsule_adoption_pins_immutable_uid_from_preflight():
    assert validate_adoption_provider_identity(
        expected_uid='provider-generation-1',
        observed_uid='provider-generation-1',
        resource_version='123',
    ) is None


@pytest.mark.parametrize(
    'expected_uid,observed_uid,resource_version',
    [
        ('', 'live-uid', '123'),
        ('expected-uid', '', '123'),
        ('expected-uid', 'expected-uid', ''),
        ('previous-generation', 'recreated-generation', '124'),
    ],
)
def test_new_tenant_adoption_rejects_missing_or_replaced_provider_identity(
    expected_uid: str, observed_uid: str, resource_version: str,
):
    with pytest.raises(ValueError, match='UID|resourceVersion'):
        validate_adoption_provider_identity(
            expected_uid=expected_uid,
            observed_uid=observed_uid,
            resource_version=resource_version,
        )
