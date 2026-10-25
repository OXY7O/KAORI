"""Check written Gherkin scenario completeness using existing pytest contract suite.

This is a source/specification contract, not an execution or UAT PASS.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENGINEERING = ROOT / 'docs' / 'engineering'
FEATURES = ENGINEERING / 'uat' / 'features'
CATALOG = ENGINEERING / 'KAORI_UAT_SCENARIO_CATALOG.md'
CASES = ENGINEERING / 'KAORI_UAT_ALL_CASES.md'
CATALOG_IDS = re.compile(
    r'^\| \x60(UAT-[A-Z]+-\d{3})\x60 \| (Positive|Negative) \| '
    r'(Both|UI|Non-UI) \| (High|Medium|Low) \|',
    re.MULTILINE,
)
CASE_IDS = re.compile(r'^### (UAT-[A-Z]+-\d{3}) —', re.M)
SCENARIO = re.compile(r'^  Scenario: (UAT-[A-Z]+-\d{3}) - ', re.M)


def test_gherkin_and_all_case_register_match_catalog_ids() -> None:
    catalog = CATALOG_IDS.findall(CATALOG.read_text(encoding='utf-8'))
    expected = {scenario_id for scenario_id, *_ in catalog}
    cases = CASE_IDS.findall(CASES.read_text(encoding='utf-8'))
    feature_files = sorted(FEATURES.glob('*.feature'))
    scenario_ids = [
        scenario_id
        for file in feature_files
        for scenario_id in SCENARIO.findall(file.read_text(encoding='utf-8'))
    ]
    assert len(expected) == len(catalog) == 143
    assert len(feature_files) == 21
    assert len(cases) == len(set(cases)) == 143
    assert len(scenario_ids) == len(set(scenario_ids)) == 143
    assert expected == set(cases) == set(scenario_ids)


def test_all_case_procedures_include_required_evidence_and_safety() -> None:
    sections = re.split(
        r'^### UAT-[A-Z]+-\d{3} —.*$',
        CASES.read_text(encoding='utf-8'),
        flags=re.M,
    )[1:]
    assert len(sections) == 143
    for case in sections:
        for field in (
            '**Preconditions:**', '**Steps:**', '**Expected results:**',
            '**Required evidence:**', '**Isolation / cleanup:**',
            '**Automation mapping:**', '**Execution:** NOT RUN',
        ):
            assert field in case, field
        assert re.search(r'(?m)^1\. ', case)
        assert re.search(r'(?m)^2\. ', case)
        assert re.search(r'(?m)^- ', case)


def test_gherkin_has_tags_and_given_when_then_per_case() -> None:
    counts = {'first_wave': 0, 'owner_review': 0}
    for file in FEATURES.glob('*.feature'):
        text = file.read_text(encoding='utf-8')
        assert text.count('\nFeature: ') == 1
        assert text.count('\n  Background:') == 1
        matches = list(SCENARIO.finditer(text))
        assert matches
        for index, match in enumerate(matches):
            scenario_id = match.group(1)
            tag_line = text[:match.start()].rstrip().splitlines()[-1]
            assert '@' + scenario_id in tag_line
            assert '@specified' in tag_line
            assert ('@first_wave' in tag_line) != ('@owner_review' in tag_line)
            counts['first_wave'] += int('@first_wave' in tag_line)
            counts['owner_review'] += int('@owner_review' in tag_line)
            stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.end():stop]
            for keyword in ('Given', 'When', 'Then'):
                assert re.search(rf'(?m)^    {keyword} ', body), scenario_id
    assert counts == {'first_wave': 14, 'owner_review': 129}


def test_source_audit_never_claims_executed_uat() -> None:
    """Inspected assertions do not imply scenario execution or human acceptance."""
    matrix = (ENGINEERING / 'uat' / 'SCENARIO_COVERAGE_MATRIX.md').read_text(encoding='utf-8')
    audit = (ENGINEERING / 'KAORI_UAT_TEST_MAPPING_AUDIT.md').read_text(encoding='utf-8')
    rows = [line for line in matrix.splitlines() if line.startswith('| `UAT-')]
    assert len(rows) == 143
    assert all(line.endswith('| NOT RUN / PENDING |') for line in rows)
    assert '**24/143**' in matrix
    assert '**119/143**' in matrix
    assert '**0/143' in matrix
    assert '**Admission:** HOLD' in matrix

    additional_ids = (
        'UAT-AUT-001',
        'UAT-AUT-004',
        'UAT-AUT-005',
        'UAT-TEN-003',
        'UAT-TEN-006',
        'UAT-TEN-008',
        'UAT-RPT-002',
        'UAT-RPT-005',
        'UAT-RPT-007',
    )
    section = audit.split('## Supplemental source assertion audit', 1)[1].split(
        '## Prioritized implementation decisions', 1
    )[0]
    for scenario_id in additional_ids:
        assert any(line.startswith(f'| `{scenario_id}` |') for line in section.splitlines())
        matrix_line = next(line for line in rows if line.startswith(f'| `{scenario_id}` |'))
        assert '([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md))' in matrix_line
    assert 'NOT RUN' in section
    assert 'PENDING' in section
    assert 'complete scenario-to-node-to-runtime acceptance' in section


def test_pilot_manifest_source_trace_is_explicitly_not_executed() -> None:
    """Cross-branch node references are planned mappings, not candidate-bound UAT PASS."""
    matrix = (ENGINEERING / 'uat' / 'SCENARIO_COVERAGE_MATRIX.md').read_text(encoding='utf-8')
    audit = (ENGINEERING / 'KAORI_UAT_TEST_MAPPING_AUDIT.md').read_text(encoding='utf-8')
    pilot = audit.split('## Exact pilot manifest-to-test traceability', 1)[1]
    pilot_ids = ('UAT-AUT-002', 'UAT-UIX-006', 'UAT-RPT-003', 'UAT-TEN-004')
    nodes = (
        'test_invalid_credentials_return_generic_failure_without_account_disclosure',
        'test_notification_center_filters_and_rows_survive_htmx_reset',
        'test_queued_report_failure_persists_failed_detail_without_pending_poll',
        'test_failed_generated_report_detail_is_truthful_and_responsive',
        'test_reports_generate_wizard_negative_submission_is_scoped_and_reviewable',
        'test_namespace_allocation_submit_rechecks_committed_capacity_before_provider_write',
        'test_tenant_allocation_change_rejected_submit_records_no_provider_write',
    )
    assert 'seven exact node IDs' in pilot
    assert '**27**' in pilot
    assert '**24 independently attributable screenshot artifacts and 24 trace artifacts**' in pilot
    assert '`provider_readback`' in pilot
    assert '`committed_state`' in pilot
    assert '`activity_audit`' in pilot
    assert 'NOT RUN' in pilot
    assert 'PENDING' in pilot
    for node_name in nodes:
        assert node_name in pilot
    for scenario_id in pilot_ids:
        assert f'`{scenario_id}`' in pilot
        row = next(line for line in matrix.splitlines() if line.startswith(f'| `{scenario_id}` |'))
        assert row.endswith('| NOT RUN / PENDING |')
        assert 'Pilot #1728:' in row
        assert '([audit](../KAORI_UAT_TEST_MAPPING_AUDIT.md))' in row
