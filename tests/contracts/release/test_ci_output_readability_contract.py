from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
WORKFLOW = ROOT / '.github/workflows/quality.yml'


def test_pytest_success_output_is_captured_instead_of_streaming_progress_dots() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'run_pytest_capture' in source
    assert 'mktemp' in source
    assert 'pytest "$@" >"$log_file" 2>&1' in source
    assert 'pytest -qq' not in source


def test_pytest_failure_output_is_failure_first_and_bounded() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'short test summary info' in source
    assert 'FAILURES' in source
    assert 'tail -n' in source
    assert 'First actionable failure' in source


def test_static_verifier_output_is_grouped_instead_of_streamed_as_long_prose() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'run_command_capture' in source
    assert 'STATIC_OUTPUT_DIR' in source
    for group in (
        'Foundation & Governance',
        'Reports/Domain Contracts',
        'Kubernetes & Platform Contracts',
        'Code Quality & Type Safety',
    ):
        assert group in source


def test_successful_static_groups_emit_one_operator_row_instead_of_one_pass_per_verifier() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert "printf '  PASS — %s\\n' \"$label\"" not in source
    assert 'group_pass_count' in source
    assert "PASS — KAORI %s · %s checks" in source
    assert 'Detailed PASS output is retained in' in source


def test_failed_static_verifier_remains_failure_first_and_names_the_check() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert "printf '  FAIL — %s\\n' \"$label\"" in source
    assert 'First actionable failure' in source
    assert 'Diagnostic excerpt' in source
    assert 'Next action' in source


def test_raw_ci_diagnostics_are_uploaded_as_artifacts() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'Upload Static Diagnostics' in workflow
    assert 'Upload Test Diagnostics' in workflow
    assert 'Upload Smoke Diagnostics' in workflow
    assert 'tmp/ci-artifacts/static-output' in workflow
    assert 'tmp/ci-artifacts/test-output' in workflow


def test_admission_summary_reports_real_failure_state_instead_of_hardcoded_pass() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'RESULT=' in workflow
    assert 'FIRST_FAILURE=' in workflow
    assert '--result "$RESULT"' in workflow
    assert '--first-failure "$FIRST_FAILURE"' in workflow
    assert '--result PASS' not in workflow
