from app.integrations.contracts.base import OperationAdapter, RuntimeAdapter
from app.integrations.contracts.capabilities import (
    CapabilityDefinition,
    CompatibilityProfileDefinition,
    normalize_capability_keys,
)
from app.integrations.contracts.exceptions import (
    IntegrationContractViolation,
    IntegrationError,
    IntegrationInstanceNotFound,
    IntegrationNotRegistered,
    IntegrationOperationNotSupported,
)
from app.integrations.contracts.results import (
    CapabilitySnapshot,
    DiagnosticResult,
    HealthFactor,
    HealthState,
    IntegrationOperationResult,
    RuntimeState,
)

__all__ = [
    'CapabilityDefinition',
    'CapabilitySnapshot',
    'CompatibilityProfileDefinition',
    'DiagnosticResult',
    'HealthFactor',
    'HealthState',
    'IntegrationContractViolation',
    'IntegrationError',
    'IntegrationInstanceNotFound',
    'IntegrationNotRegistered',
    'IntegrationOperationNotSupported',
    'IntegrationOperationResult',
    'OperationAdapter',
    'RuntimeAdapter',
    'RuntimeState',
    'normalize_capability_keys',
]
