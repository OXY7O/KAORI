"""GitHub App Integration Kernel descriptor is exact and inert until admission."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.integrations.source_control.source_control.providers.github import kernel_contract


def test_provider_kernel_descriptor_reuses_existing_integration_types():
    module = kernel_contract.integration_module
    implementation = kernel_contract.provider_implementation
    assert module.integration_type == 'source_control'
    assert module.domain_key == 'source_control'
    assert module.capability_key == 'source_control'
    assert module.workspace_endpoint == 'integrations.source_control'
    assert module.operation_queues['runtime.validate'] == 'integration-validation'
    assert module.operation_queues['runtime.health'] == 'integration-runtime'
    assert module.operation_queues['connection.test'] == 'inline'
    assert implementation.integration_type == 'source_control'
    assert implementation.provider_key == 'github'
    assert implementation.adapter_key == 'github_rest_v3'
    assert implementation.record_model.__tablename__ == 'source_control_installations'


def test_explicitly_planned_github_cannot_register_descriptor(monkeypatch):
    from app.integrations.kernel.registry import registry

    registered_before = tuple(registry.all())
    monkeypatch.setattr(kernel_contract, 'provider_kind', lambda *_: SimpleNamespace(available=False))
    assert kernel_contract.register_after_admission() is False
    assert tuple(registry.all()) == registered_before


def test_provider_wiring_is_explicit_and_admission_gated():
    repo_root = Path(__file__).resolve().parents[2]
    core = (repo_root / 'app/integrations/kernel/registry.py').read_text()
    assert "if provider_kind('source_control', 'github').available:" in core
    assert 'register_after_admission()' in core


def test_failure_recorder_sanitizes_provider_exception():
    from types import SimpleNamespace

    canonical = SimpleNamespace(
        last_error=None, readiness_status='validation_required',
        health_status=None, last_checked_at=None,
    )
    record = SimpleNamespace(integration_instance=canonical)
    kernel_contract._record_failure(record, RuntimeError('credential-leak-example'))
    assert canonical.readiness_status == 'blocked'
    assert canonical.health_status == 'unhealthy'
    assert canonical.last_checked_at is not None
    assert 'credential-leak-example' not in canonical.last_error
