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


def test_rc_expanded_steps_report_executed_evidence_not_only_a_summary() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    for marker in (
        'RC admission · resolving accepted staging SHA',
        'RC admission · waiting for exact staging Full Admission success',
        'RC admission · Full Admission PASS',
        'RC publication · building exact production image',
        'RC security · HIGH/CRITICAL image scan PASS',
        'RC runtime · production readiness and baseline DAST PASS',
        'RC publication · reserving immutable Git tag',
        'RC evidence · immutable digest recorded',
        'RC attestation · signing SPDX SBOM predicate',
        'RC attestation · signing SLSA provenance predicate',
        'RC verification · SPDX and SLSA source lineage PASS',
        'RC publication · creating GitHub prerelease',
    ):
        assert marker in workflow

    # The immutable tag, digest and attestations remain authoritative.
    assert 'quality_run_id=%s' in workflow
    assert '--severity HIGH,CRITICAL --scanners vuln' in workflow
    assert 'sbom-attestation-statements.jsonl' in workflow
    assert 'provenance-attestation-statements.jsonl' in workflow
    assert 'if-no-files-found: error' in workflow
