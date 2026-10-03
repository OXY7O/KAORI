from __future__ import annotations

from app.artifact_registry.security.contracts import RegistrySecurityEvidence
from app.artifact_registry.security.harbor import collect_harbor_security
from app.models.harbor import HarborInstance
from app.models.integration import IntegrationInstance
from app.models.registry_artifact import RegistryArtifact


class UnsupportedRegistrySecurityProvider(RuntimeError):
    pass


def collect_registry_security(
    instance: IntegrationInstance,
    artifacts: list[RegistryArtifact],
) -> RegistrySecurityEvidence:
    if instance.integration_type != 'registry':
        raise UnsupportedRegistrySecurityProvider(
            f'Integration instance {instance.id} is not a Registry integration.'
        )
    if instance.provider_key == 'harbor':
        source = HarborInstance.query.filter_by(integration_instance_id=instance.id).first()
        if source is None:
            raise RuntimeError('Harbor provider configuration is missing for this Registry integration.')
        return collect_harbor_security(source, artifacts)
    raise UnsupportedRegistrySecurityProvider(
        f'Registry provider {instance.provider_key!r} does not have a security evidence collector yet.'
    )
