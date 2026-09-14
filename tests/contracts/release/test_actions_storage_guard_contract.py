from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github' / 'workflows' / 'quality.yml'


def _step_block(workflow: str, step_name: str, next_step_name: str) -> str:
    start = workflow.index(f'- name: {step_name}')
    end = workflow.index(f'- name: {next_step_name}', start)
    return workflow[start:end]


def test_successful_functional_admission_does_not_store_test_diagnostics() -> None:
    workflow = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    upload = _step_block(workflow, 'Upload Test Diagnostics', 'Cleanup Test Dependencies')

    assert 'if: ${{ failure() }}' in upload
    assert 'if: ${{ always() }}' not in upload
    assert 'retention-days: 1' in upload
