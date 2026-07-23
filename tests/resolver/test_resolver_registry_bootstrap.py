import pytest

from app.integrations.resolver_bootstrap import (
    ACTION_DEPLOYMENT_RESTART,
    ResolverBootstrapSettings,
    build_resolver_registry,
    registry_fingerprint,
)
from app.resolver.contracts import ResolverError


def test_enabled_action_builds_deterministic_registry():
    settings = ResolverBootstrapSettings((ACTION_DEPLOYMENT_RESTART,), ('payments',))
    first = build_resolver_registry(settings)
    second = build_resolver_registry(settings)
    assert first.registered_actions() == (ACTION_DEPLOYMENT_RESTART,)
    assert registry_fingerprint(first) == registry_fingerprint(second)


def test_kubernetes_enablement_requires_explicit_namespace_allowlist():
    with pytest.raises(ResolverError, match='explicit namespace allowlist'):
        build_resolver_registry(ResolverBootstrapSettings((ACTION_DEPLOYMENT_RESTART,), ()))


def test_unknown_action_fails_closed():
    with pytest.raises(ResolverError, match='Unknown enabled resolver actions'):
        build_resolver_registry(ResolverBootstrapSettings(('kubernetes.secret.patch',), ('payments',)))
