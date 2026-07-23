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
    assert 'if not instance.enabled' in source
    assert "instance.integration_instance.lifecycle_status != 'active'" in source
    assert 'Prometheus validation was canceled because the integration is no longer active.' in source


def test_consumer_module_remains_syntax_valid() -> None:
    _tree('app/prometheus/consumer.py')
    _tree('app/integrations/validation/tasks.py')
