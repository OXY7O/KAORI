from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github/workflows/quality.yml'
DEVELOPER_WORKFLOW = ROOT / '.github/workflows/developer-check.yml'
DELIVERY = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
POLICY = ROOT / 'scripts/ci_admission_policy.py'
COMPAT = ROOT / 'scripts/ci_admission.py'

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
    spec = importlib.util.spec_from_file_location('kaori_ci_admission_policy', POLICY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_delivery_governance_authorizes_tree_fingerprint_reuse_without_weakening_uat() -> None:
    source = read(DELIVERY)
    assert '**Governance Version:** 2.1' in source
    assert 'Full Admission' in source
    assert 'exact evidence reuse' in source.lower()
    assert 'authority fingerprint' in source.lower()
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
    first_expensive = source.index('full-admission-gates:')
    assert first_profile < first_expensive


def test_admission_publishes_non_authoritative_exact_sha_commit_status() -> None:
    source = read(WORKFLOW)
    admission = source.split('\n  admission:', 1)[1]

    assert '  statuses: write' in source
    assert 'name: Publish Admission Commit Status' in admission
    assert 'continue-on-error: true' in admission
    assert 'SOURCE_SHA: ${{ needs.validation-profile.outputs.source_sha }}' in admission
    assert 'KAORI CI / Admission' in admission
    assert 'statuses/$SOURCE_SHA' in admission
    assert '$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID' in admission
    assert 'state=success' in admission
    assert 'state=failure' in admission


def test_staging_evidence_lookup_accepts_direct_and_sequenced_admission_parents() -> None:
    workflow = read(WORKFLOW)
    policy_source = read(POLICY)

    assert '--workflow quality.yml' in workflow
    assert '--workflow developer-check.yml' in workflow
    assert "evidence.add_argument('--workflow', action='append')" in policy_source
    assert 'workflows = (workflow,) if isinstance(workflow, str) else tuple(workflow)' in policy_source


def test_issue_branch_pushes_do_not_trigger_governed_full_admission() -> None:
    source = read(WORKFLOW)
    assert '  push:' in source
    assert '      - kaori/staging' in source
    assert '      - main' in source
    assert '      - "release/**"' in source
    assert '      - "kaori/**"' not in source


def test_ready_feature_pr_is_sequenced_through_developer_check_before_admission() -> None:
    quality = read(WORKFLOW)
    developer = read(DEVELOPER_WORKFLOW)
    pull_request_block = quality.split('pull_request:', 1)[1].split('permissions:', 1)[0]

    assert '      - kaori/staging' not in pull_request_block
    assert '      - main' in pull_request_block
    assert 'ready_for_review' in pull_request_block

    assert 'uses: ./.github/workflows/quality.yml' in developer
    assert "needs.developer-check.result == 'success'" in developer
    assert 'github.event.pull_request.draft == false' in developer
    assert (
        'github.event.pull_request.draft == true'
        not in developer.split('\n  route:', 1)[1].split('\n  toolchain:', 1)[0]
    )

    # Reusable Full Admission still receives the caller PR context and therefore
    # retains the existing feature-PR routing guard inside the called workflow.
    assert "github.base_ref == 'kaori/staging'" in quality
    assert "startsWith(github.head_ref, 'kaori/')" in quality
    assert "github.head_ref != 'kaori/staging'" in quality


def test_full_admission_comprehensive_gates_use_native_fail_fast_matrix() -> None:
    source = read(WORKFLOW)
    matrix = source.split('\n  full-admission-gates:', 1)[1].split('\n  integration-smoke:', 1)[0]

    assert 'needs: validation-profile' in matrix
    assert 'strategy:' in matrix
    assert 'fail-fast: true' in matrix
    assert 'max-parallel: 2' in matrix
    assert matrix.index('gate: functional') < matrix.index('gate: static')
    assert 'Keep the longest comprehensive gate in the first scheduling wave.' in matrix
    for gate in (
        'gate: static',
        'gate: security',
        'gate: functional',
        'gate: frontend',
        'gate: runtime',
    ):
        assert gate in matrix

    assert 'static-quality:' not in source
    assert 'static-security:' not in source
    assert 'functional-tests:' not in source
    assert '\n  frontend:' not in source
    assert 'production-runtime:' not in source


def test_matrix_cancellation_keeps_resource_cleanup_and_fail_closed_admission() -> None:
    source = read(WORKFLOW)
    matrix = source.split('\n  full-admission-gates:', 1)[1].split('\n  integration-smoke:', 1)[0]
    admission = source.split('\n  admission:', 1)[1]

    assert "if: ${{ always() && matrix.gate == 'functional' }}" in matrix
    assert "if: ${{ always() && matrix.gate == 'runtime' }}" in matrix
    assert 'docker rm -f "$GATE_CONTAINER"' in matrix
    assert 'full-admission-gates' in admission
    assert 'FULL_GATES: ${{ needs.full-admission-gates.result }}' in admission
    assert '[[ "$FULL_GATES" == "success" ]]' in admission
    assert 'selected Full Admission matrix failed or was cancelled' in admission


def test_full_admission_test_taxonomy_evidence_is_aggregated_across_gate_owners() -> None:
    source = read(WORKFLOW)
    matrix = source.split('\n  full-admission-gates:', 1)[1].split('\n  integration-smoke:', 1)[0]
    admission = source.split('\n  admission:', 1)[1]

    assert 'Upload Static JUnit Evidence' in matrix
    assert 'Upload Functional JUnit Evidence' in matrix
    assert 'contract-migration.xml' in matrix
    assert 'release-suite.xml' in matrix
    assert 'e2e.xml' in matrix

    assert 'actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1' in admission
    assert 'Download Static JUnit Evidence' in admission
    assert 'Download Functional JUnit Evidence' in admission
    assert 'Write Full Test Taxonomy Summary' in admission
    assert 'id: full_test_evidence' in admission
    assert "steps.full_test_evidence.outcome == 'success'" in admission
    assert 'TEST_EVIDENCE: ${{ steps.full_test_evidence.outcome }}' in admission
    assert 'TEST_EVIDENCE_OUTCOME: ${{ steps.full_test_evidence.outcome }}' in admission
    assert 'Full test taxonomy evidence — $TEST_EVIDENCE' in admission
    assert '--junit tmp/ci-artifacts/admission-junit/static/contract-migration.xml' in admission
    assert '--junit tmp/ci-artifacts/admission-junit/functional/release-suite.xml' in admission
    assert '--junit tmp/ci-artifacts/admission-junit/functional/e2e.xml' in admission


def test_full_admission_junit_handoff_survives_failed_job_reruns() -> None:
    source = read(WORKFLOW)
    matrix = source.split('\n  full-admission-gates:', 1)[1].split('\n  integration-smoke:', 1)[0]
    admission = source.split('\n  admission:', 1)[1]

    static_name = 'full-admission-junit-static-${{ github.run_id }}'
    functional_name = 'full-admission-junit-functional-${{ github.run_id }}'

    assert f'name: {static_name}' in matrix
    assert f'name: {functional_name}' in matrix
    assert f'name: {static_name}' in admission
    assert f'name: {functional_name}' in admission
    assert 'full-admission-junit-static-${{ github.run_id }}-${{ github.run_attempt }}' not in source
    assert 'full-admission-junit-functional-${{ github.run_id }}-${{ github.run_attempt }}' not in source
    assert matrix.count('overwrite: true') >= 2
    assert '--run-attempt "$GITHUB_RUN_ATTEMPT"' in admission


def test_successful_matrix_preserves_per_gate_evidence_vocabulary() -> None:
    source = read(WORKFLOW)
    admission = source.split('\n  admission:', 1)[1]

    for option in (
        '--static-quality "${{ needs.full-admission-gates.result }}"',
        '--static-security "${{ needs.full-admission-gates.result }}"',
        '--functional-tests "${{ needs.full-admission-gates.result }}"',
        '--frontend "${{ needs.full-admission-gates.result }}"',
        '--production-runtime "${{ needs.full-admission-gates.result }}"',
    ):
        assert option in admission


def test_profile_version_and_compatibility_wrapper_use_current_authority() -> None:
    policy = load_policy()
    compat_source = read(COMPAT)
    workflow_source = read(WORKFLOW)

    assert policy.PROFILE_VERSION == '3'
    assert 'KAORI_PROFILE_VERSION: "3"' in workflow_source
    assert 'import ci_admission_policy as policy' in compat_source
    assert "arguments[0] == 'test-summary'" in compat_source


def test_fast_profiles_wire_transition_lineage_verification_before_reuse() -> None:
    source = read(WORKFLOW)

    assert 'Verify Lineage' in source
    assert 'ci_admission.py verify-lineage' in source
    for token in (
        '--profile "$PROFILE"',
        '--source-sha "$SOURCE_SHA"',
        '--source-tree "$SOURCE_TREE"',
        '--expected-before "${EXPECTED_BEFORE:-}"',
        '--expected-base "${EXPECTED_BASE:-}"',
        '--evidence-source-sha "$EVIDENCE_SOURCE_SHA"',
        '--evidence-source-tree "$EVIDENCE_SOURCE_TREE"',
    ):
        assert token in source
    assert 'lineage_reusable' in source
    assert 'lineage_reason' in source


def test_full_admission_keeps_canonical_evidence_inventory_under_concise_job_names() -> None:
    source = read(WORKFLOW)
    policy = load_policy()

    assert set(policy.FULL_GATE_NAMES) == REQUIRED_FULL_GATES - {'KAORI CI Admission'}
    for job_name in (
        'name: Static & Governance',
        'name: Security',
        'name: Functional Tests',
        'name: Frontend',
        'name: Runtime & DAST',
        'name: CI Admission',
    ):
        assert job_name in source
    for command in (
        'bash scripts/quality_gate.sh --static',
        'bash .github/ci/run-security-static.sh',
        'bash scripts/quality_gate.sh --tests',
        'bash scripts/quality_gate.sh --frontend',
        'trivy image',
        'bash .github/ci/run-runtime-validation.sh',
    ):
        assert command in source


def test_policy_routes_transitions_to_evidence_lookup_even_for_validation_authority_changes() -> None:
    policy = load_policy()

    staging_pr = policy.resolve_profile(
        event_name='pull_request',
        ref='refs/pull/100/merge',
        base_ref='kaori/staging',
        head_ref='kaori/tech-debt-39-resource-utilization',
        changed_paths=('app/reports/example.py',),
    )
    assert (staging_pr.profile, staging_pr.execution) == ('pr-integration', 'fast')

    sensitive_staging_pr = policy.resolve_profile(
        event_name='pull_request',
        ref='refs/pull/102/merge',
        base_ref='kaori/staging',
        head_ref='td55-artifact-redirect-auth-fix',
        changed_paths=('scripts/ci_admission.py', '.github/workflows/quality.yml'),
    )
    assert (sensitive_staging_pr.profile, sensitive_staging_pr.execution) == ('pr-integration', 'fast')
    assert 'authority' in sensitive_staging_pr.reason.lower()

    staging_push = policy.resolve_profile(
        event_name='push',
        ref='refs/heads/kaori/staging',
        base_ref='',
        head_ref='',
        changed_paths=('scripts/ci_admission.py',),
    )
    assert (staging_push.profile, staging_push.execution) == ('staging-integration', 'fast')

    promotion = policy.resolve_profile(
        event_name='pull_request',
        ref='refs/pull/101/merge',
        base_ref='main',
        head_ref='kaori/staging',
        changed_paths=('scripts/ci_admission.py',),
    )
    assert (promotion.profile, promotion.execution) == ('promotion', 'fast')

    post_promotion = policy.resolve_profile(
        event_name='push',
        ref='refs/heads/main',
        base_ref='',
        head_ref='',
        changed_paths=('scripts/ci_admission.py',),
    )
    assert (post_promotion.profile, post_promotion.execution) == ('post-promotion', 'fast')


def test_non_transition_source_context_remains_conservative_full_if_invoked() -> None:
    policy = load_policy()
    branch = policy.resolve_profile(
        event_name='push',
        ref='refs/heads/kaori/tech-debt-39-resource-utilization',
        base_ref='',
        head_ref='',
        changed_paths=('app/reports/example.py',),
    )
    assert (branch.profile, branch.execution) == ('full', 'full')


def test_authority_fingerprint_changes_only_for_validation_authority_entries() -> None:
    policy = load_policy()
    base = (
        ('.github/workflows/quality.yml', '100644', 'aaa'),
        ('scripts/ci_admission.py', '100755', 'bbb'),
        ('scripts/ci_admission_policy.py', '100755', 'ccc'),
        ('app/reports/example.py', '100644', 'ddd'),
    )
    app_changed = (
        ('.github/workflows/quality.yml', '100644', 'aaa'),
        ('scripts/ci_admission.py', '100755', 'bbb'),
        ('scripts/ci_admission_policy.py', '100755', 'ccc'),
        ('app/reports/example.py', '100644', 'eee'),
    )
    authority_changed = (
        ('.github/workflows/quality.yml', '100644', 'fff'),
        ('scripts/ci_admission.py', '100755', 'bbb'),
        ('scripts/ci_admission_policy.py', '100755', 'ccc'),
        ('app/reports/example.py', '100644', 'ddd'),
    )

    assert policy.authority_fingerprint_from_entries(base) == policy.authority_fingerprint_from_entries(app_changed)
    assert policy.authority_fingerprint_from_entries(base) != policy.authority_fingerprint_from_entries(
        authority_changed
    )


def test_evidence_reuse_requires_tree_fingerprint_profile_timestamp_and_all_required_gates() -> None:
    policy = load_policy()
    evidence = {
        'result': 'PASS',
        'profile': 'full',
        'profile_version': '3',
        'source_sha': 'admitted-head',
        'source_tree': 'tree123',
        'authority_fingerprint': 'authority123',
        'full_admission_run_id': 426,
        'run_attempt': 1,
        'workflow_ref': 'OXY7O/KAORI/.github/workflows/quality.yml@refs/pull/60/merge',
        'created_at': datetime.now(UTC).isoformat(),
        'gates': {gate: 'success' for gate in REQUIRED_FULL_GATES - {'KAORI CI Admission'}},
    }

    accepted = policy.evidence_reuse_decision(
        evidence,
        current_tree='tree123',
        current_authority_fingerprint='authority123',
        required_profile_version='3',
    )
    assert accepted.reusable is True
    assert accepted.full_admission_run_id == 426
    assert accepted.source_sha == 'admitted-head'

    wrong_sha_same_tree = dict(evidence)
    wrong_sha_same_tree['source_sha'] = 'different-admitted-sha'
    accepted_transition_sha = policy.evidence_reuse_decision(
        wrong_sha_same_tree,
        current_tree='tree123',
        current_authority_fingerprint='authority123',
        required_profile_version='3',
    )
    assert accepted_transition_sha.reusable is True
    assert accepted_transition_sha.source_sha == 'different-admitted-sha'

    wrong_tree = policy.evidence_reuse_decision(
        evidence,
        current_tree='tree999',
        current_authority_fingerprint='authority123',
        required_profile_version='3',
    )
    assert wrong_tree.reusable is False
    assert 'tree' in wrong_tree.reason.lower()

    wrong_authority = policy.evidence_reuse_decision(
        evidence,
        current_tree='tree123',
        current_authority_fingerprint='authority999',
        required_profile_version='3',
    )
    assert wrong_authority.reusable is False
    assert 'fingerprint' in wrong_authority.reason.lower()

    wrong_profile = policy.evidence_reuse_decision(
        evidence,
        current_tree='tree123',
        current_authority_fingerprint='authority123',
        required_profile_version='4',
    )
    assert wrong_profile.reusable is False
    assert 'profile' in wrong_profile.reason.lower()

    failed = dict(evidence)
    failed['gates'] = dict(evidence['gates'])
    failed['gates']['Frontend Reproducibility'] = 'skipped'
    rejected = policy.evidence_reuse_decision(
        failed,
        current_tree='tree123',
        current_authority_fingerprint='authority123',
        required_profile_version='3',
    )
    assert rejected.reusable is False
    assert 'frontend' in rejected.reason.lower()


def test_full_evidence_schema_contains_authority_fingerprint() -> None:
    policy = load_policy()
    evidence = policy.build_full_evidence(
        source_sha='abc123',
        source_tree='tree123',
        authority_fingerprint='authority123',
        run_id=500,
        run_attempt=1,
        workflow_ref='OXY7O/KAORI/.github/workflows/quality.yml@refs/pull/60/merge',
        gates={gate: 'success' for gate in policy.FULL_GATE_NAMES},
    )
    assert evidence['profile_version'] == '3'
    assert evidence['authority_fingerprint'] == 'authority123'
    assert evidence['source_tree'] == 'tree123'


def test_remote_evidence_lookup_error_falls_back_instead_of_raising(monkeypatch) -> None:
    policy = load_policy()
    monkeypatch.setattr(policy, '_candidate_lineage', lambda *args, **kwargs: [('abc123', 'tree123')])

    def fail_lookup(*args, **kwargs):
        raise OSError('GitHub API unavailable')

    monkeypatch.setattr(policy, '_github_request', fail_lookup)
    decision = policy.find_remote_full_evidence(
        repository='OXY7O/KAORI',
        token='token',
        workflow='quality.yml',
        start_sha='abc123',
        current_tree='tree123',
        current_authority_fingerprint='authority123',
    )
    assert decision.reusable is False
    assert 'lookup' in decision.reason.lower()


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
        evidence='REUSED Full Admission #426',
        fresh_checks=('merge lineage', 'migration/import smoke', 'E2E smoke'),
        reused_coverage=('static', 'security', 'full tests', 'frontend', 'runtime', 'DAST'),
        duration='3m 12s',
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


def test_quality_gate_exposes_fast_smoke_phase_and_captures_pytest_progress_noise() -> None:
    source = read(QUALITY_GATE)
    assert '--smoke' in source
    assert 'run_smoke' in source
    assert 'GITHUB_STEP_SUMMARY' in source
    assert '--tb=short' in source
    assert 'run_pytest_capture' in source
    assert 'pytest "$@" >"$log_file" 2>&1' in source
    assert 'pytest -qq' not in source


def test_artifact_redirect_drops_github_authorization_on_cross_host_https() -> None:
    policy = load_policy()
    request = policy.urllib.request.Request(
        'https://api.github.com/repos/OXY7O/KAORI/actions/artifacts/123/zip',
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': 'Bearer github-token',
        },
    )

    handler = policy._GitHubArtifactRedirectHandler()
    redirected = handler.redirect_request(
        request,
        None,
        302,
        'Found',
        {},
        'https://productionresultssa0.blob.core.windows.net/actions-results/example.zip?sig=signed',
    )

    assert redirected is not None
    assert redirected.full_url.startswith('https://productionresultssa0.blob.core.windows.net/')
    assert redirected.get_header('Authorization') is None
    assert redirected.get_header('Accept') == 'application/vnd.github+json'


def test_artifact_redirect_rejects_https_downgrade() -> None:
    policy = load_policy()
    request = policy.urllib.request.Request(
        'https://api.github.com/repos/OXY7O/KAORI/actions/artifacts/123/zip',
        headers={'Authorization': 'Bearer github-token'},
    )
    handler = policy._GitHubArtifactRedirectHandler()

    try:
        handler.redirect_request(request, None, 302, 'Found', {}, 'http://example.invalid/artifact.zip')
    except ValueError as exc:
        assert 'https' in str(exc).lower()
    else:
        raise AssertionError('Artifact redirect downgrade must fail closed.')
