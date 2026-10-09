from __future__ import annotations

import pytest

from app.kubernetes.tenant.discovery_adoption import validate_adoption_provider_identity


def test_native_and_capsule_adoption_pins_exact_uid_and_version_from_preflight():
    assert validate_adoption_provider_identity(
        expected_uid='provider-generation-1',
        observed_uid='provider-generation-1',
        expected_resource_version='123',
        observed_resource_version='123',
    ) is None


@pytest.mark.parametrize(
    'expected_uid,observed_uid,expected_version,observed_version',
    [
        ('', 'live-uid', '123', '123'),
        ('expected-uid', '', '123', '123'),
        ('expected-uid', 'expected-uid', '', '123'),
        ('expected-uid', 'expected-uid', '123', ''),
        ('previous-generation', 'recreated-generation', '123', '124'),
        ('expected-uid', 'expected-uid', '123', '124'),
    ],
)
def test_new_tenant_adoption_rejects_missing_or_changed_provider_identity(
    expected_uid: str, observed_uid: str,
    expected_version: str, observed_version: str,
):
    with pytest.raises(ValueError, match='UID|resourceVersion'):
        validate_adoption_provider_identity(
            expected_uid=expected_uid,
            observed_uid=observed_uid,
            expected_resource_version=expected_version,
            observed_resource_version=observed_version,
        )
