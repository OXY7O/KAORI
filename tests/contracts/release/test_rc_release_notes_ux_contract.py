from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github/workflows/publish-staging-image.yml'


def _release_notes_block() -> str:
    source = WORKFLOW.read_text(encoding='utf-8')
    start = source.index('- name: Build RC Notes')
    end = source.index('- name: Publish RC Release', start)
    return source[start:end]


def test_rc_release_notes_use_operator_friendly_information_architecture() -> None:
    block = _release_notes_block()

    for heading in (
        '## Overview',
        '## Highlights',
        '## Operational Impact',
        '## Validation Evidence',
        '## Known Limitations',
        '## Promotion Status',
        '### Immutable Evidence',
    ):
        assert heading in block

    assert '## What Changed' not in block


def test_rc_release_notes_preserve_immutable_lineage_and_uat_boundary() -> None:
    block = _release_notes_block()

    for token in (
        '${CANDIDATE_TAG}',
        '${ACCEPTED_SHA}',
        '${QUALITY_RUN_ID}',
        '${KAORI_IMAGE_DIGEST}',
        '${KAORI_IMAGE_REF}',
        'does not imply UAT or production acceptance',
        'must not rebuild application bits',
    ):
        assert token in block
