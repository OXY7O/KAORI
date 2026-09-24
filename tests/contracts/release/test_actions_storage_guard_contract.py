from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github' / 'workflows' / 'quality.yml'
DEVELOPER_WORKFLOW = ROOT / '.github' / 'workflows' / 'developer-check.yml'


def _step_block(workflow: str, step_name: str, next_step_name: str | None = None) -> str:
    start = workflow.index(f'- name: {step_name}')
    end = workflow.index(f'- name: {next_step_name}', start) if next_step_name else len(workflow)
    return workflow[start:end]


def test_successful_functional_admission_does_not_store_test_diagnostics() -> None:
    workflow = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    upload = _step_block(workflow, 'Upload Test Diagnostics', 'Cleanup Test Dependencies')

    assert 'if: ${{ failure() }}' in upload
    assert 'if: ${{ always() }}' not in upload
    assert 'retention-days: 1' in upload


def test_transient_diagnostics_are_failure_only_and_short_lived() -> None:
    workflow = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    developer = DEVELOPER_WORKFLOW.read_text(encoding='utf-8')

    quality_steps = (
        ('Upload Static Diagnostics', 'Checkout Source'),
        ('Upload Security Diagnostics', 'Checkout Source'),
        ('Upload Runtime Diagnostics', 'Cleanup Runtime Resources'),
        ('Upload Smoke Diagnostics', 'Cleanup Smoke Dependencies'),
    )
    for step_name, next_step_name in quality_steps:
        upload = _step_block(workflow, step_name, next_step_name)
        assert 'if: ${{ failure() }}' in upload, f'{step_name} must be failure-only'
        assert 'if: ${{ always() }}' not in upload, f'{step_name} must not run on success'
        assert 'retention-days: 3' in upload, f'{step_name} must retain for 3 days'

    browser_upload = _step_block(developer, 'Upload Browser Diagnostics')
    assert 'if: ${{ failure() }}' in browser_upload
    assert 'if: ${{ always() }}' not in browser_upload
    assert 'retention-days: 3' in browser_upload


def test_full_admission_evidence_keeps_governed_retention() -> None:
    workflow = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    upload = _step_block(workflow, 'Upload Admission Evidence', 'Write Admission Summary')

    assert 'retention-days: 14' in upload
