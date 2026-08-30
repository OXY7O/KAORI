from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github/workflows/quality.yml'
DELIVERY = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
POLICY = ROOT / 'scripts/ci_admission.py'

REQUIRED_FULL_GATES = {
    'Static, Architecture, and Governance',
    'Secrets, SAST, Dependencies, and Workflow Security',
    'Functional and Integration Tests',
    'Frontend Reproducibility',
    'Production Image, Container Security, Runtime, and DAST',
    'KAORI CI Admission',
}


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_policy() -> ModuleType:
    assert POLICY.exists(), 'Progressive CI policy helper is not implemented yet.'
    spec = importlib.util.spec_from_file_location('kaori_ci_admission', POLICY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_delivery_governance_v2_authorizes_exact_evidence_reuse_without_weakening_uat() -> None:
    source = read(DELIVERY)
    assert '**Governance Version:** 2.0' in source
    assert 'Full Admission' in source
    assert 'exact evidence reuse' in source.lower()
    assert 'tree' in source.lower()
    assert 'FALLBACK' in source
    assert 'Local UAT' in source
    assert 'never bypass or reuse conclusions' not in source


def test_workflow_exposes_progressive_profiles_before_expensive_full_jobs() -> None:
    source = read(WORKFLOW)
    policy_source = read(POLICY)
    for token in (
        'validation-profile:',
        'FALLBACK',
        'GITHUB_STEP_SUMMARY',
    ):
        assert token in source
    for display_name in (
        'Full Admission',
        'PR Integration',
        'Staging Integration',
        'Promotion',
        'Post-promotion',
    ):
        assert display_name in policy_source

    first_profile = source.index('validation-profile:')
    first_expensive = source.index('static-quality:')
    assert first_profile < first_expensive


def test_full_admission_keeps_the_existing_comprehensive_gate_inventory() -> None:
    source = read(WORKFLOW)
    for gate in REQUIRED_FULL_GATES:
        assert gate in source
    for command in (
        'bash scripts/quality_gate.sh --static',
        'bash .github/ci/run-security-static.sh',
        'bash scripts/quality_gate.sh --tests',
        'bash scripts/quality_gate.sh --frontend',
        'trivy image',
        'bash .github/ci/run-runtime-validation.sh',
    ):
        assert command in source


def test_policy_routes_normal_delivery_profiles_and_sensitive_changes_fail_closed() -> None:
    policy = load_policy()

    branch = policy.resolve_profile(
        event_name='push',
        ref='refs/heads/kaori/tech-debt-39-resource-utilization',
        base_ref='',
        head_ref='',
        changed_paths=('app/reports/example.py',),
    )
    assert (branch.profile, branch.execution) == ('full', 'full')

    staging_pr = policy.resolve_profile(
        event_name='pull_request',
        ref='refs/pull/100/merge',
        base_ref='kaori/staging',
        head_ref='kaori/tech-debt-39-resource-utilization',
        changed_paths=('app/reports/example.py',),
    )
    assert (staging_pr.profile, staging_pr.execution) == ('pr-integration', 'fast')

    staging_push = policy.resolve_profile(
        event_name='push',
        ref='refs/heads/kaori/staging',
        base_ref='',
        head_ref='',
        changed_paths=('app/reports/example.py',),
    )
    assert (staging_push.profile, staging_push.execution) == ('staging-integration', 'fast')

    promotion = policy.resolve_profile(
        event_name='pull_request',
        ref='refs/pull/101/merge',
        base_ref='main',
        head_ref='kaori/staging',
        changed_paths=('app/reports/example.py',),
    )
    assert (promotion.profile, promotion.execution) == ('promotion', 'fast')

    post_promotion = policy.resolve_profile(
        event_name='push',
        ref='refs/heads/main',
        base_ref='',
        head_ref='',
        changed_paths=('app/reports/example.py',),
    )
    assert (post_promotion.profile, post_promotion.execution) == ('post-promotion', 'fast')

    sensitive = policy.resolve_profile(
        event_name='pull_request',
        ref='refs/pull/102/merge',
        base_ref='kaori/staging',
        head_ref='kaori/tech-debt-55-progressive-ci-evidence-reuse',
        changed_paths=('.github/workflows/quality.yml',),
    )
    assert sensitive.profile == 'pr-integration'
    assert sensitive.execution == 'full'
    assert 'sensitive' in sensitive.reason.lower()


def test_evidence_reuse_requires_exact_sha_tree_profile_and_all_required_gates() -> None:
    policy = load_policy()
    evidence = {
        'result': 'PASS',
        'profile_version': '2',
        'source_sha': 'abc123',
        'source_tree': 'tree123',
        'full_admission_run_id': 420,
        'gates': {gate: 'success' for gate in REQUIRED_FULL_GATES - {'KAORI CI Admission'}},
    }

    accepted = policy.evidence_reuse_decision(
        evidence,
        current_sha='abc123',
        current_tree='tree123',
        required_profile_version='2',
    )
    assert accepted.reusable is True
    assert accepted.full_admission_run_id == 420

    wrong_tree = policy.evidence_reuse_decision(
        evidence,
        current_sha='abc123',
        current_tree='tree999',
        required_profile_version='2',
    )
    assert wrong_tree.reusable is False
    assert 'tree' in wrong_tree.reason.lower()

    failed = dict(evidence)
    failed['gates'] = dict(evidence['gates'])
    failed['gates']['Frontend Reproducibility'] = 'skipped'
    rejected = policy.evidence_reuse_decision(
        failed,
        current_sha='abc123',
        current_tree='tree123',
        required_profile_version='2',
    )
    assert rejected.reusable is False
    assert 'frontend' in rejected.reason.lower()


def test_merge_lineage_reuse_requires_expected_parents_and_equivalent_tree() -> None:
    policy = load_policy()

    staging = policy.staging_lineage_reuse_decision(
        parent_shas=('old-staging', 'admitted-head'),
        merge_tree='admitted-tree',
        expected_staging_parent='old-staging',
        admitted_head_sha='admitted-head',
        admitted_tree='admitted-tree',
    )
    assert staging.reusable is True

    staging_bad_tree = policy.staging_lineage_reuse_decision(
        parent_shas=('old-staging', 'admitted-head'),
        merge_tree='reconstructed-tree',
        expected_staging_parent='old-staging',
        admitted_head_sha='admitted-head',
        admitted_tree='admitted-tree',
    )
    assert staging_bad_tree.reusable is False
    assert 'tree' in staging_bad_tree.reason.lower()

    promotion = policy.promotion_lineage_reuse_decision(
        parent_shas=('old-main', 'accepted-staging'),
        merge_tree='accepted-tree',
        expected_main_parent='old-main',
        accepted_staging_sha='accepted-staging',
        accepted_tree='accepted-tree',
    )
    assert promotion.reusable is True


def test_operator_pass_summary_is_structured_and_omits_fake_failure_field() -> None:
    policy = load_policy()
    summary = policy.render_operator_summary(
        result='PASS',
        profile='Staging Integration',
        commit_sha='dffd49d5',
        tree_sha='3bc5c0ac',
        evidence='REUSED Full Admission #346',
        fresh_checks=('merge lineage', 'migration/import smoke', 'E2E smoke'),
        reused_coverage=('static', 'security', 'full tests', 'frontend', 'runtime', 'DAST'),
        duration='4m 12s',
        first_failure=None,
        next_action='Sync exact staging SHA for Local UAT',
    )
    ordered_tokens = (
        'Result',
        'Profile',
        'Commit SHA',
        'Tree SHA',
        'Evidence',
        'Duration',
        'Coverage summary',
        'Fresh checks',
        'Reused checks',
        'Next action',
    )
    positions = [summary.index(token) for token in ordered_tokens]
    assert positions == sorted(positions)
    assert 'PASS' in summary
    assert 'Staging Integration' in summary
    assert 'First actionable failure' not in summary
    assert 'job failed' not in summary.lower()


def test_operator_failure_summary_is_failure_first_and_actionable() -> None:
    policy = load_policy()
    summary = policy.render_operator_summary(
        result='FAIL',
        profile='PR Integration',
        commit_sha='abc123',
        tree_sha='tree123',
        evidence='Fresh Full Admission',
        fresh_checks=('release contracts',),
        reused_coverage=(),
        duration='1m 09s',
        first_failure='tests/reports/test_example.py::test_missing_evidence — expected Not Available, received 0%',
        next_action='Repair missing-evidence presentation logic',
    )
    assert 'FAIL' in summary
    assert 'First actionable failure' in summary
    assert 'tests/reports/test_example.py::test_missing_evidence' in summary
    assert 'expected Not Available, received 0%' in summary
    assert 'Next action' in summary


def test_quality_gate_exposes_fast_smoke_phase_and_captures_pytest_progress_noise() -> None:
    source = read(QUALITY_GATE)
    assert '--smoke' in source
    assert 'run_smoke' in source
    assert 'GITHUB_STEP_SUMMARY' in source
    assert '--tb=short' in source
    assert 'run_pytest_capture' in source
    assert 'pytest "$@" >"$log_file" 2>&1' in source
    assert 'pytest -qq' not in source
