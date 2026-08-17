from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from flask import Flask

from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver_adapter import (
    KubernetesDeploymentRestartAdapter,
    NamespaceGuardrail,
)
from app.intelligence.resolver.contracts import ResolverError
from app.intelligence.resolver.registry import ResolverRegistry

EXTENSION_KEY = 'kaori_resolver_registry'
FINGERPRINT_KEY = 'kaori_resolver_registry_fingerprint'
ACTION_DEPLOYMENT_RESTART = 'kubernetes.deployment.restart'
SUPPORTED_RESOLVER_ACTIONS = frozenset({ACTION_DEPLOYMENT_RESTART})
CATALOG_VALIDATION_NAMESPACE = '__kaori_catalog_validation__'


@dataclass(frozen=True, slots=True)
class ResolverBootstrapSettings:
    enabled_actions: tuple[str, ...]
    kubernetes_namespaces: tuple[str, ...]


def parse_csv(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.split(',')
    elif isinstance(value, Iterable):
        values = value
    else:
        raise ResolverError('Resolver configuration must be a comma-separated string or iterable.')
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


def settings_from_config(config: Mapping[str, object]) -> ResolverBootstrapSettings:
    return ResolverBootstrapSettings(
        enabled_actions=parse_csv(config.get('RESOLVER_ENABLED_ACTIONS')),
        kubernetes_namespaces=parse_csv(config.get('RESOLVER_KUBERNETES_ALLOWED_NAMESPACES')),
    )


def registry_fingerprint(registry: ResolverRegistry) -> str:
    descriptors = []
    for action in registry.registered_actions():
        descriptor = registry.describe(action)
        descriptors.append(
            {
                'action_key': descriptor.action_key,
                'capability_keys': list(descriptor.capability_keys),
                'compatibility_profiles': list(descriptor.compatibility_profiles),
                'rollback_required': descriptor.rollback_required,
                'verification_required': descriptor.verification_required,
            }
        )
    payload = json.dumps(descriptors, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def build_resolver_registry(settings: ResolverBootstrapSettings) -> ResolverRegistry:
    registry = ResolverRegistry()
    unknown = set(settings.enabled_actions) - SUPPORTED_RESOLVER_ACTIONS
    if unknown:
        raise ResolverError(f'Unknown enabled resolver actions: {", ".join(sorted(unknown))}.')
    if ACTION_DEPLOYMENT_RESTART in settings.enabled_actions:
        if not settings.kubernetes_namespaces:
            raise ResolverError('Kubernetes resolver enablement requires an explicit namespace allowlist.')
        registry.register(
            KubernetesDeploymentRestartAdapter(
                namespace_guardrail=NamespaceGuardrail(
                    allowed_namespaces=frozenset(settings.kubernetes_namespaces),
                )
            )
        )
    return registry


def build_resolver_contract_registry() -> ResolverRegistry:
    """Build a validation-only registry for source-controlled runbook publication.

    This registry proves that the adapter contract exists in the current KAORI build without
    registering the action for execution. The sentinel namespace prevents it from being a useful
    execution registry even if a caller accidentally retains it.
    """

    registry = ResolverRegistry()
    registry.register(
        KubernetesDeploymentRestartAdapter(
            namespace_guardrail=NamespaceGuardrail(
                allowed_namespaces=frozenset({CATALOG_VALIDATION_NAMESPACE}),
            )
        )
    )
    return registry


def init_resolver_registry(app: Flask) -> ResolverRegistry:
    settings = settings_from_config(app.config)
    signing_key = str(app.config.get('RESOLVER_TOKEN_SIGNING_KEY') or '')
    if settings.enabled_actions and len(signing_key) < 32:
        raise ResolverError('Enabled resolver actions require RESOLVER_TOKEN_SIGNING_KEY with at least 32 characters.')
    registry = build_resolver_registry(settings)
    fingerprint = registry_fingerprint(registry)
    app.extensions[EXTENSION_KEY] = registry
    app.extensions[FINGERPRINT_KEY] = fingerprint
    app.config['RESOLVER_REGISTRY_FINGERPRINT'] = fingerprint
    return registry


def get_resolver_registry(app: Flask) -> ResolverRegistry:
    registry = app.extensions.get(EXTENSION_KEY)
    if not isinstance(registry, ResolverRegistry):
        raise ResolverError('Resolver registry has not been initialized for this process.')
    return registry
