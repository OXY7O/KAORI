from pathlib import Path


def test_shared_resolver_filters_canonical_lifecycle() -> None:
    source = Path('app/integrations/resolver.py').read_text()

    assert "IntegrationInstance.lifecycle_status == 'active'" in source
    assert "lifecycle == 'active'" in source
    assert 'Canonical lifecycle' in source


def test_validation_worker_delegates_to_shared_lifecycle_guard() -> None:
    source = Path('app/integrations/validation/tasks.py').read_text()

    assert 'ensure_provider_operational' in source
    assert 'def _ensure_instance_operational' not in source
    assert 'ensure_provider_operational(instance, provider_type=provider_type)' in source


def test_shared_lifecycle_guard_checks_provider_and_canonical_state() -> None:
    source = Path('app/integrations/lifecycle.py').read_text()

    assert 'def ensure_provider_operational' in source
    assert "getattr(provider_record, 'enabled', False)" in source
    assert "getattr(canonical, 'enabled', False)" in source
    assert "lifecycle_status != 'active'" in source
