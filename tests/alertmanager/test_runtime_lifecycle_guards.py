from types import SimpleNamespace

import pytest

from app.alertmanager import resolver as resolver_module
from app.integrations.lifecycle import ensure_provider_operational


def _instance(*, enabled=True, canonical_enabled=True, lifecycle='active'):
    return SimpleNamespace(
        enabled=enabled,
        integration_instance=SimpleNamespace(
            enabled=canonical_enabled,
            lifecycle_status=lifecycle,
        ),
    )


def test_worker_guard_accepts_active_instance():
    ensure_provider_operational(_instance(), provider_type='alertmanager')


@pytest.mark.parametrize(
    ('instance', 'message'),
    [
        (_instance(enabled=False), 'provider instance is disabled'),
        (_instance(canonical_enabled=False), 'integration is no longer active'),
        (_instance(lifecycle='deleting'), 'integration is no longer active'),
    ],
)
def test_worker_guard_rejects_non_operational_instance(instance, message):
    with pytest.raises(RuntimeError, match=message):
        ensure_provider_operational(instance, provider_type='alertmanager')


def test_alertmanager_resolver_rejects_non_active_canonical_lifecycle(monkeypatch):
    monkeypatch.setattr(resolver_module, '_selector_required', lambda _binding: False)
    instance = SimpleNamespace(
        enabled=True,
        readiness_status='ready',
        last_status='connected',
        capabilities=['alerts_v2'],
        integration_instance=SimpleNamespace(enabled=True, lifecycle_status='deleting'),
    )
    binding = SimpleNamespace(
        enabled=True,
        validation_status='ready',
        selector_json=None,
        binding_role='primary',
        priority=10,
        id=7,
    )

    candidate = resolver_module._evaluate_binding(
        binding,
        instance,
        required_capabilities=('alerts_v2',),
    )

    assert candidate.eligible is False
    assert 'lifecycle deleting blocks source selection' in candidate.decision_reason
