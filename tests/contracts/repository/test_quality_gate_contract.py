from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]


def test_quality_workflow_runs_all_mandatory_gates() -> None:
    workflow = (ROOT / '.github/workflows/quality.yml').read_text(encoding='utf-8')

    for required in (
        'scripts/quality_gate.sh --static',
        'scripts/quality_gate.sh --tests',
        'scripts/quality_gate.sh --frontend',
        'docker build --target production',
    ):
        assert required in workflow


def test_release_requires_quality_workflow_before_publish() -> None:
    workflow = (ROOT / '.github/workflows/release-image.yml').read_text(encoding='utf-8')

    assert 'uses: ./.github/workflows/quality.yml' in workflow
    assert 'needs: quality' in workflow


def test_source_archive_is_git_based_and_hygiene_gated() -> None:
    script = (ROOT / 'scripts/build_source_archive.sh').read_text(encoding='utf-8')

    assert 'git archive' in script
    assert 'verify_source_hygiene.sh' in script
    assert 'requires a clean Git working tree' in script
