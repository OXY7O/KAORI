"""Regression contract for the bounded branch-ruleset evidence handover (#4216).

This test validates documentation assertions, not effective GitHub settings.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'docs/engineering/KAORI_BRANCH_RULESETS_EVIDENCE.md'


def test_ruleset_handover_distinguishes_configured_rules_from_effective_enforcement() -> None:
    text = EVIDENCE.read_text(encoding='utf-8')
    assert 'PARTIALLY VERIFIED, NOT ACCEPTED' in text
    for ruleset_id in (
        '26596521',
        '26684718',
        '26685250',
        '26685572',
        '26685631',
        '26685877',
        '26687947',
        '26688007',
        '26688106',
    ):
        assert ruleset_id in text
    for observed_value in (
        'refs/heads/main',
        'refs/heads/kaori/staging',
        'deletion',
        'non_fast_forward',
        'required_approving_review_count: 0',
        'required_review_thread_resolution: false',
        'Developer Check',
        'KAORI CI / Admission',
        'Website Validation',
        'Docs Validation',
    ):
        assert observed_value in text

    gaps = {
        'Required PR review / resolved conversations': 'GAP VERIFIED',
        'Exact required check contexts': 'VERIFIED (configured for staging)',
        'Website and Docs repository protections': 'PARTIALLY VERIFIED',
    }
    for control, expected_state in gaps.items():
        rows = [line for line in text.splitlines() if line.startswith(f'| {control} |')]
        assert len(rows) == 1, control
        assert f'| {expected_state}' in rows[0], control

    for control in (
        'Direct-push prevention / merge method policy',
        'Repository Actions permissions / runner groups / environments',
        'Organization 2FA / app permissions / emergency access',
        'main',
    ):
        assert control in text
    assert 'NOT VERIFIED (effective)' in text
    assert 'GitHub Settings mutations' in text


def test_ruleset_handover_preserves_admission_and_security_boundaries() -> None:
    text = EVIDENCE.read_text(encoding='utf-8')
    for required in (
        'external-fork negative test',
        'kaori/review/staging-uat',
        'NOT VERIFIED',
        'NO-GO',
        'Full Admission',
        'GitHub Project Status',
        'privileged self-hosted runners',
    ):
        assert required in text


def test_ruleset_handover_flags_skipped_required_checks_without_claiming_staging_acceptance() -> None:
    evidence = EVIDENCE.read_text(encoding='utf-8')
    assert 'Required-status skipped-job hazard' in evidence
    assert 'skipped by a job-level' in evidence
    assert 'even as a required check' in evidence
    for issue, pull in (('#4278', '#4239'), ('#141', '#141'), ('#79', '#79')):
        assert issue in evidence and pull in evidence
    for required in (
        'before checkout',
        'Draft PR to official staging',
        'PENDING',
        'Real fork negative test',
        '403 Resource not accessible by integration',
        'different conditions',
        'single-maintainer deadlock',
    ):
        assert required in evidence
    assert 'NOT ACCEPTED' in evidence
    assert 'NO-GO' in evidence
