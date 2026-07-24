import ast
from pathlib import Path


def _tree(path: str) -> ast.Module:
    return ast.parse(Path(path).read_text())


def test_consumer_resolves_sources_with_operation_capabilities() -> None:
    source = Path('app/prometheus/consumer.py').read_text()
    assert 'required_technical_capabilities=required_capabilities' in source
    assert 'fallback_used=' in source
    assert "DEFAULT_RANGE_CAPABILITIES = ('range_query',)" in source


def test_validation_worker_uses_shared_operational_guard_directly() -> None:
    tasks_source = Path('app/integrations/validation/tasks.py').read_text()
    assert 'def _ensure_instance_operational(' not in tasks_source
    assert "ensure_provider_operational(instance, provider_type='prometheus')" in tasks_source



def test_prometheus_validation_calls_guard_before_runtime_refresh() -> None:
    source = Path('app/integrations/validation/tasks.py').read_text()
    prometheus_branch = source.index("provider_type == 'prometheus'")
    guard_call = source.index(
        "ensure_provider_operational(instance, provider_type='prometheus')",
        prometheus_branch,
    )
    refresh_call = source.index('refresh_and_record(', prometheus_branch)

    assert guard_call < refresh_call


def test_consumer_and_shared_guard_modules_remain_syntax_valid() -> None:
    _tree('app/prometheus/consumer.py')
    _tree('app/integrations/lifecycle.py')
    _tree('app/integrations/validation/tasks.py')
