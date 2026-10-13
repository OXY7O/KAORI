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
CATALOG_IDS = re.compile(r'^\| .(UAT-[A-Z]+-\d{3}). \| (Positive|Negative) \| (Both|UI|Non-UI) \| (High|Medium|Low) \|', re.M)
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
    assert len(expected) == len(catalog) == 91
    assert len(feature_files) == 18
    assert len(cases) == len(set(cases)) == 91
    assert len(scenario_ids) == len(set(scenario_ids)) == 91
    assert expected == set(cases) == set(scenario_ids)


def test_all_case_procedures_include_required_evidence_and_safety() -> None:
    sections = re.split(
        r'^### UAT-[A-Z]+-\d{3} —.*$',
        CASES.read_text(encoding='utf-8'),
        flags=re.M,
    )[1:]
    assert len(sections) == 91
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
    assert counts == {'first_wave': 14, 'owner_review': 77}
