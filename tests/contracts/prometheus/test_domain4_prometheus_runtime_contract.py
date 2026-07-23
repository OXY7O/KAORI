import ast
from pathlib import Path


def _tree(path: str) -> ast.Module:
    return ast.parse(Path(path).read_text())


def test_consumer_resolves_sources_with_operation_capabilities() -> None:
    source = Path('app/prometheus/consumer.py').read_text()
    assert 'required_technical_capabilities=required_capabilities' in source
    assert 'fallback_used=' in source
    assert "DEFAULT_RANGE_CAPABILITIES = ('range_query',)" in source


def test_validation_worker_blocks_inactive_prometheus_instances() -> None:
    source = Path('app/integrations/validation/tasks.py').read_text()

    helper_start = source.index('def _ensure_instance_operational(')
    helper_end = source.index('\ndef ', helper_start + 1)
    helper_source = source[helper_start:helper_end]

    assert "getattr(instance, 'enabled', False)" in helper_source
    assert "getattr(canonical, 'enabled', False)" in helper_source
    assert "getattr(canonical, 'lifecycle_status', '')" in helper_source
    assert "!= 'active'" in helper_source

    prometheus_branch = source.index("if provider_type == 'prometheus':", helper_end)
    guard_call = source.index(
        "_ensure_instance_operational(instance, provider_type='prometheus')",
        prometheus_branch,
    )
    provider_call = source.index('refresh_and_record(', guard_call)

    assert guard_call < provider_call


def test_consumer_module_remains_syntax_valid() -> None:
    _tree('app/prometheus/consumer.py')
    _tree('app/integrations/validation/tasks.py')
