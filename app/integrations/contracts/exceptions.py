from __future__ import annotations


class IntegrationError(RuntimeError):
    """Base exception for provider-neutral integration orchestration."""


class IntegrationNotRegistered(IntegrationError):
    pass


class IntegrationOperationNotSupported(IntegrationError):
    pass


class IntegrationInstanceNotFound(IntegrationError):
    pass


class IntegrationContractViolation(IntegrationError):
    pass
