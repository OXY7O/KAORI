from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.integrations.kernel.registry import get_integration
from app.models.integration import IntegrationInstance


@dataclass(frozen=True, slots=True)
class RegistryInventoryEligibility:
    eligible: bool
    readiness: str
    compatibility_status: str
    reason: str


def inventory_read_contract_eligible(readiness: str | None, compatibility_status: str | None) -> bool:
    normalized_readiness = str(readiness or 'validation_required').strip().lower()
    normalized_compatibility = str(compatibility_status or '').strip().lower()
    if normalized_readiness == 'ready':
        return True
    return (
        normalized_readiness == 'degraded'
        and normalized_compatibility == 'compatible_with_warnings'
    )


def registry_inventory_eligibility(
    identity: IntegrationInstance,
    *,
    provider_record: Any | None = None,
) -> RegistryInventoryEligibility:
    readiness = str(identity.readiness_status or 'validation_required').strip().lower()
    if identity.integration_type != 'registry':
        return RegistryInventoryEligibility(
            eligible=False,
            readiness=readiness,
            compatibility_status='',
            reason='Inventory synchronization requires a canonical Registry integration identity.',
        )
    if not identity.enabled:
        return RegistryInventoryEligibility(
            eligible=False,
            readiness=readiness,
            compatibility_status='',
            reason='Registry provider is disabled.',
        )
    if identity.lifecycle_status != 'active':
        return RegistryInventoryEligibility(
            eligible=False,
            readiness=readiness,
            compatibility_status='',
            reason='Registry provider lifecycle is not active.',
        )

    module = get_integration('registry')
    record = provider_record or module.require_record_for_canonical(int(identity.id))
    runtime_state = module.runtime_state(record)
    compatibility_status = str(
        (runtime_state.snapshot.metadata or {}).get('compatibility_status') or ''
    ).strip().lower()
    runtime_readiness = str(runtime_state.readiness or readiness).strip().lower()

    if inventory_read_contract_eligible(runtime_readiness, compatibility_status):
        reason = (
            'Required Registry read contract is validated with Extended Support attention.'
            if runtime_readiness == 'degraded'
            else 'Registry provider is fully ready for inventory collection.'
        )
        return RegistryInventoryEligibility(
            eligible=True,
            readiness=runtime_readiness,
            compatibility_status=compatibility_status,
            reason=reason,
        )

    if runtime_readiness == 'degraded':
        reason = (
            'Degraded provider is not inventory-eligible because compatibility is not an '
            'Extended Support compatible-with-warnings result.'
        )
    elif runtime_readiness == 'validation_required':
        reason = 'Run Full Validation before Artifact Registry inventory synchronization.'
    elif runtime_readiness == 'blocked':
        reason = 'Registry provider readiness is blocked; resolve validation failures before synchronization.'
    else:
        reason = f'Registry provider readiness {runtime_readiness!r} is not inventory-eligible.'
    return RegistryInventoryEligibility(
        eligible=False,
        readiness=runtime_readiness,
        compatibility_status=compatibility_status,
        reason=reason,
    )
