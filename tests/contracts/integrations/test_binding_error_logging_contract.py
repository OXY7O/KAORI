from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_unexpected_binding_failure_preserves_stack_trace() -> None:
    routes = (ROOT / 'app/integrations/routes.py').read_text(encoding='utf-8')
    binding_response = routes.split('def _binding_response(', 1)[1]
    exception_block = binding_response.split('except Exception as exc:', 1)[1].split('else:', 1)[0]

    assert 'current_app.logger.exception(' in exception_block
    assert 'record_operational_activity(' in exception_block
    assert exception_block.index('current_app.logger.exception(') < exception_block.index(
        'record_operational_activity('
    )
    assert "'reason': type(exc).__name__" in exception_block
