from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_unexpected_binding_failure_preserves_stack_trace() -> None:
    binding_web = (ROOT / 'app/integrations/binding_web.py').read_text(encoding='utf-8')
    binding_response = binding_web.split('def binding_response(', 1)[1]
    exception_block = binding_response.split('except Exception as exc:', 1)[1].split('else:', 1)[0]

    assert 'current_app.logger.exception(' in exception_block
    assert 'record_operational_activity(' in exception_block
    assert exception_block.index('current_app.logger.exception(') < exception_block.index(
        'record_operational_activity('
    )
    assert "'reason': type(exc).__name__" in exception_block


def test_binding_response_guards_optional_saved_context_before_success_feedback() -> None:
    binding_web = (ROOT / 'app/integrations/binding_web.py').read_text(encoding='utf-8')
    binding_response = binding_web.split('def binding_response(', 1)[1]
    success_path = binding_response.split('created_binding = create_source_binding(', 1)[1].split(
        'except ValueError as exc:', 1
    )[0]

    assert 'if source is None or cluster is None or binding is None:' in success_path
    assert "raise ValueError('KAORI could not resolve the saved source binding context.')" in success_path
