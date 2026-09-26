from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.managed_resources import (
    ManagedResourceSecretMaterial,
    validate_managed_resource_intent,
)


def _intent(*, kind='tls', mode='platform_tls', source_reference=None):
    return SimpleNamespace(
        resource_kind=kind,
        mode=mode,
        source_reference=source_reference,
        resource_name='kaori-platform-tls' if kind == 'tls' else 'kaori-registry-pull',
        namespace=SimpleNamespace(
            id=11,
            namespace='payments-prod',
            environment=SimpleNamespace(tenant_id='tenant-a'),
        ),
        tenant_id='tenant-a',
    )


def test_platform_tls_is_preferred_and_requires_no_namespace_secret_material() -> None:
    intent = _intent()
    validate_managed_resource_intent(intent, material=None)


def test_tls_compatibility_mode_requires_ephemeral_tls_material() -> None:
    intent = _intent(mode='namespace_tls_compat', source_reference='vault://tenant-a/tls')
    with pytest.raises(ValueError, match='TLS material'):
        validate_managed_resource_intent(intent, material=None)

    material = ManagedResourceSecretMaterial(
        data={'tls.crt': 'certificate', 'tls.key': 'private-key'},
    )
    validate_managed_resource_intent(intent, material=material)


def test_registry_secret_requires_ephemeral_dockerconfig_material() -> None:
    intent = _intent(
        kind='registry',
        mode='image_pull_secret',
        source_reference='vault://tenant-a/registry',
    )
    with pytest.raises(ValueError, match='registry material'):
        validate_managed_resource_intent(intent, material=None)

    material = ManagedResourceSecretMaterial(data={'.dockerconfigjson': '{"auths":{}}'})
    validate_managed_resource_intent(intent, material=material)


def test_managed_modes_cannot_be_reclassified_across_resource_kinds() -> None:
    with pytest.raises(ValueError, match='TLS'):
        validate_managed_resource_intent(_intent(kind='tls', mode='image_pull_secret'), material=None)

    with pytest.raises(ValueError, match='Registry'):
        validate_managed_resource_intent(_intent(kind='registry', mode='platform_tls'), material=None)


def test_secret_material_repr_is_redacted() -> None:
    material = ManagedResourceSecretMaterial(data={'tls.key': 'secret'})
    assert 'secret' not in repr(material)
    assert 'tls.key' not in repr(material)
