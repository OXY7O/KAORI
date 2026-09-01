#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET  # nosec B405
from collections.abc import Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import ci_admission_policy as policy  # noqa: E402

# Backward-compatible policy exports for existing contract imports.
PROFILE_VERSION = policy.PROFILE_VERSION
EVIDENCE_MAX_AGE_SECONDS = policy.EVIDENCE_MAX_AGE_SECONDS
FULL_GATE_NAMES = policy.FULL_GATE_NAMES
PROFILE_DISPLAY = policy.PROFILE_DISPLAY
ProfileDecision = policy.ProfileDecision
ReuseDecision = policy.ReuseDecision
authority_fingerprint_from_entries = policy.authority_fingerprint_from_entries
compute_authority_fingerprint = policy.compute_authority_fingerprint
resolve_profile = policy.resolve_profile
evidence_reuse_decision = policy.evidence_reuse_decision
staging_lineage_reuse_decision = policy.staging_lineage_reuse_decision
promotion_lineage_reuse_decision = policy.promotion_lineage_reuse_decision
transition_lineage_reuse_decision = policy.transition_lineage_reuse_decision
render_operator_summary = policy.render_operator_summary
build_full_evidence = policy.build_full_evidence
find_remote_full_evidence = policy.find_remote_full_evidence
_GitHubArtifactRedirectHandler = policy._GitHubArtifactRedirectHandler
_github_request = policy._github_request
_candidate_lineage = policy._candidate_lineage

TEST_TAXONOMY_LABELS = (
    'Unit Tests',
    'Functional Tests',
    'Integration Tests',
    'Security Regression',
    'Rendering / UI',
    'Contract Tests',
    'Migration Tests',
    'End-to-End Smoke',
)


def _testcase_taxonomy(testcase: ET.Element) -> str:
    file_path = str(testcase.attrib.get('file', '')).replace('\\', '/')
    class_path = str(testcase.attrib.get('classname', '')).replace('.', '/')
    evidence_path = f'{file_path} {class_path}'

    if 'tests/unit/' in evidence_path:
        return 'Unit Tests'
    if 'tests/integration/' in evidence_path:
        return 'Integration Tests'
    if 'tests/security/' in evidence_path:
        return 'Security Regression'
    if 'tests/rendering/' in evidence_path:
        return 'Rendering / UI'
    if 'tests/contracts/' in evidence_path:
        return 'Contract Tests'
    if 'tests/migrations/' in evidence_path:
        return 'Migration Tests'
    if 'tests/e2e/' in evidence_path:
        return 'End-to-End Smoke'
    return 'Functional Tests'


def _junit_outcome(testcase: ET.Element) -> str:
    if testcase.find('failure') is not None:
        return 'failed'
    if testcase.find('error') is not None:
        return 'error'
    if testcase.find('skipped') is not None:
        return 'skipped'
    return 'passed'


def _test_word(count: int) -> str:
    return 'test' if count == 1 else 'tests'


def render_test_taxonomy_summary(junit_paths: Sequence[Path]) -> str:
    counts = {label: {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0} for label in TEST_TAXONOMY_LABELS}
    for junit_path in junit_paths:
        # Inputs are trusted pytest JUnit files generated inside the current CI workspace.
        root = ET.parse(junit_path).getroot()  # nosec B314
        for testcase in root.iter('testcase'):
            label = _testcase_taxonomy(testcase)
            counts[label][_junit_outcome(testcase)] += 1

    lines: list[str] = []
    for label in TEST_TAXONOMY_LABELS:
        bucket = counts[label]
        passed = bucket['passed']
        failed = bucket['failed']
        errors = bucket['error']
        skipped = bucket['skipped']
        total = passed + failed + errors + skipped
        if total == 0:
            continue

        if failed or errors:
            details = [f'{failed} failed'] if failed else []
            if errors:
                details.append(f'{errors} error' if errors == 1 else f'{errors} errors')
            if passed:
                details.append(f'{passed} passed')
            if skipped:
                details.append(f'{skipped} skipped')
            lines.append(f'❌ {label} · {" / ".join(details)}')
        elif passed:
            detail = f'{total} {_test_word(total)}'
            if skipped:
                detail = f'{passed} passed / {skipped} skipped'
            lines.append(f'✅ {label} · {detail}')
        else:
            lines.append(f'⚠️ {label} · {skipped} skipped')
    return '\n'.join(lines)


def _run_test_summary(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description='Render KAORI pytest taxonomy summary')
    parser.add_argument('--junit', action='append', required=True)
    args = parser.parse_args(argv)
    print(render_test_taxonomy_summary(tuple(Path(path) for path in args.junit)))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    if arguments and arguments[0] == 'test-summary':
        return _run_test_summary(arguments[1:])
    return policy.main(arguments)


if __name__ == '__main__':
    raise SystemExit(main())
