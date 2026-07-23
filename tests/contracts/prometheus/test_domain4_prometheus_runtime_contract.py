import ast
from pathlib import Path


def _tree(path: str) -> ast.Module:
    return ast.parse(Path(path).read_text())


def test_consumer_resolves_sources_with_operation_capabilities() -> None:
    source = Path('app/prometheus/consumer.py').read_text()
    assert 'required_technical_capabilities=required_capabilities' in source
    assert 'fallback_used=' in source
    assert "DEFAULT_RANGE_CAPABILITIES = ('range_query',)" in source


def test_validation_worker_delegates_to_shared_operational_guard() -> None:
    tasks_source = Path('app/integrations/validation/tasks.py').read_text()
    lifecycle_source = Path('app/integrations/lifecycle.py').read_text()

    helper_start = tasks_source.index('def _ensure_instance_operational(')
    helper_end = tasks_source.index('\ndef ', helper_start + 1)
    helper_source = tasks_source[helper_start:helper_end]

    assert 'ensure_provider_operational(instance, provider_type=provider_type)' in helper_source
    assert "getattr(provider_record, 'enabled', False)" in lifecycle_source
    assert "getattr(canonical, 'enabled', False)" in lifecycle_source
    assert "lifecycle_status != 'active'" in lifecycle_source
    assert 'integration is no longer active' in lifecycle_source


def test_prometheus_validation_calls_guard_before_runtime_refresh() -> None:
    source = Path('app/integrations/validation/tasks.py').read_text()
    prometheus_branch = source.index("provider_type == 'prometheus'")
    guard_call = source.index(
        "_ensure_instance_operational(instance, provider_type='prometheus')",
        prometheus_branch,
    )
    refresh_call = source.index('refresh_and_record(', prometheus_branch)

    assert guard_call < refresh_call


def test_consumer_and_shared_guard_modules_remain_syntax_valid() -> None:
    _tree('app/prometheus/consumer.py')
    _tree('app/integrations/lifecycle.py')
    _tree('app/integrations/validation/tasks.py')
