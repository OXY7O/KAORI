from __future__ import annotations

from app.artifact_registry.inventory.contracts import RegistryInventoryEvidence
from app.artifact_registry.inventory.harbor import collect_harbor_inventory
from app.models.harbor import HarborInstance
from app.models.integration import IntegrationInstance


class UnsupportedRegistryInventoryProvider(RuntimeError):
    """Raised when a registered Registry provider has no normalized collector yet."""


def collect_registry_inventory(instance: IntegrationInstance) -> RegistryInventoryEvidence:
    if instance.integration_type != 'registry':
        raise UnsupportedRegistryInventoryProvider(
            f'Integration instance {instance.id} is not a Registry integration.'
        )
    if instance.provider_key == 'harbor':
        source = HarborInstance.query.filter_by(integration_instance_id=instance.id).first()
        if source is None:
            raise RuntimeError('Harbor provider configuration is missing for this Registry integration.')
        return collect_harbor_inventory(source)
    raise UnsupportedRegistryInventoryProvider(
        f'Registry provider {instance.provider_key!r} does not have an inventory collector yet.'
    )
