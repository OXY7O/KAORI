from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github' / 'workflows' / 'quality.yml'
DEVELOPER_CHECK_WORKFLOW = ROOT / '.github' / 'workflows' / 'developer-check.yml'


def _step_block(workflow: str, step_name: str, next_step_name: str) -> str:
    start = workflow.index(f'- name: {step_name}')
    end = workflow.index(f'- name: {next_step_name}', start)
    return workflow[start:end]


def _assert_failure_only_retention(upload: str, retention_days: int) -> None:
    assert 'if: ${{ failure() }}' in upload
    assert 'if: ${{ always() }}' not in upload
    assert f'retention-days: {retention_days}' in upload


def test_successful_functional_admission_does_not_store_test_diagnostics() -> None:
    workflow = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    upload = _step_block(workflow, 'Upload Test Diagnostics', 'Cleanup Test Dependencies')

    _assert_failure_only_retention(upload, 1)


def test_transient_full_admission_diagnostics_are_failure_only_and_short_lived() -> None:
    workflow = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    transient_steps = (
        ('Upload Static Diagnostics', 'Check Out Exact Source'),
        ('Upload Security Diagnostics', 'Check Out Exact Source'),
        ('Upload Runtime Diagnostics', 'Cleanup Runtime Resources'),
        ('Upload Smoke Diagnostics', 'Cleanup Smoke Dependencies'),
    )

    for step_name, next_step_name in transient_steps:
        upload = _step_block(workflow, step_name, next_step_name)
        _assert_failure_only_retention(upload, 3)


def test_developer_browser_diagnostics_are_failure_only_and_short_lived() -> None:
    workflow = DEVELOPER_CHECK_WORKFLOW.read_text(encoding='utf-8')
    start = workflow.index('- name: Upload Browser Diagnostics')
    upload = workflow[start:]

    _assert_failure_only_retention(upload, 3)


def test_immutable_full_admission_evidence_retains_governed_window() -> None:
    workflow = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    upload = _step_block(
        workflow,
        'Upload Full Admission Evidence',
        'Write Admission Summary',
    )

    assert "if: ${{ needs.validation-profile.outputs.execution == 'full' }}" in upload
    assert 'if-no-files-found: error' in upload
    assert 'retention-days: 14' in upload
