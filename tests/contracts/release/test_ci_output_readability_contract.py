import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
WORKFLOW = ROOT / '.github/workflows/quality.yml'
DEVELOPER_WORKFLOW = ROOT / '.github/workflows/developer-check.yml'
STAGING_DEPLOY_WORKFLOW = ROOT / '.github/workflows/deploy-staging-host.yml'
CI_ADMISSION = ROOT / 'scripts/ci_admission.py'


def test_pytest_success_output_is_captured_instead_of_streaming_progress_dots() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'run_pytest_capture' in source
    assert 'mktemp' in source
    assert 'pytest "$@" >"$log_file" 2>&1' in source
    assert 'pytest -qq' not in source


def test_pytest_failure_output_is_failure_first_and_bounded() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'short test summary info' in source
    assert 'FAILURES' in source
    assert 'filter_pytest_progress' in source
    assert 'tail -n 80 "$log_file" | filter_pytest_progress' in source
    assert '❌ First actionable failure' in source
    assert '➡️ Repair the first actionable failure' in source


def test_static_operator_rollup_uses_kaori_architecture_level_categories() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert "run_static_group 'Foundation & Governance'" in source
    assert "run_static_group 'Domain & Capability Contracts'" in source
    assert "run_static_group 'Engineering Quality'" in source
    assert "'Contract & Migration Safety'" in source
    assert "run_static_group 'Reports/Domain Contracts'" not in source
    assert "run_static_group 'Kubernetes & Platform Contracts'" not in source
    assert "run_static_group 'Code Quality & Type Safety'" not in source


def test_admission_summary_uses_same_architecture_level_coverage_categories() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'Domain & Capability Contracts' in workflow
    assert 'Engineering Quality' in workflow
    assert 'Reports/Domain Contracts' not in workflow
    assert 'Code Quality & Type Safety' not in workflow


def test_successful_static_groups_emit_progress_then_one_rollup_row() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'printf \'⏳ %s — %s\\n\' "$group" "$label"' in source
    assert 'group_pass_count' in source
    assert "printf '✅ %s · %s checks · ⏱ %dm %02ds\\n'" in source
    assert 'Detailed output is retained in' in source


def test_engineering_quality_verifier_timing_is_bounded_and_success_only() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    capture = source.split('run_command_capture() {', 1)[1].split('run_static_group() {', 1)[0]

    assert 'if [[ "$group" == \'Engineering Quality\' ]]' in capture
    assert 'local elapsed=$(( $(date +%s) - started ))' in capture
    assert 'printf \'✅ %s — %s · ⏱ %dm %02ds\\n\' "$group" "$label"' in capture
    assert 'if "$@" >"$log_file" 2>&1; then' in capture
    assert 'if [[ "$label" == \'Release Surface Coverage\' ]]' in capture
    assert 'return "$status"' in capture
    assert 'tail -n 60 "$log_file"' in capture
    quality = source.split("run_static_group 'Engineering Quality'", 1)[1].split('run_contract_migration_gate', 1)[0]
    assert quality.count("'python ") >= 18


def test_static_pyright_stats_stay_bounded_to_success_and_keep_full_coverage() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    capture = source.split('run_command_capture() {', 1)[1].split('run_static_group() {', 1)[0]
    static = source.split('run_static() {', 1)[1].split('run_contract_migration_gate', 1)[0]

    assert "'Pyright' 'python -m pyright --project pyrightconfig.json --stats'" in static
    assert 'if [[ "$label" == \'Pyright\' ]]' in capture
    assert 'Pyright analysis stats' in capture
    assert 'tail -n 24 "$log_file"' in capture
    assert 'if "$@" >"$log_file" 2>&1; then' in capture
    assert 'return "$status"' in capture
    assert 'tail -n 60 "$log_file"' in capture
    assert source.count("'Pyright' 'python -m pyright --project pyrightconfig.json --stats'") == 1


def test_failed_static_verifier_remains_failure_first_and_names_the_check() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'printf \'❌ %s\\n\' "$label"' in source
    assert '❌ First actionable failure' in source
    assert '📦 Diagnostic excerpt' in source
    assert '➡️ Repair %s, collect remaining findings' in source


def test_release_suite_emits_junit_for_taxonomy_summary_without_duplicate_execution() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert '--junitxml="$TEST_OUTPUT_DIR/contract-migration.xml"' in source
    assert '--junitxml="$TEST_OUTPUT_DIR/release-suite.xml"' in source
    assert '--junitxml="$TEST_OUTPUT_DIR/e2e.xml"' in source
    assert 'ci_admission.py test-summary' in source
    assert "-m 'not debug and not e2e and not contract and not migration'" in source
    assert 'Domain Characterization Tests' not in source


def test_full_admission_setup_timing_preserves_failure_and_existing_gate_ownership() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    timed = source.split('run_timed_setup() {', 1)[1].split('run_pytest_capture() {', 1)[0]
    functional = source.split('run_tests() {', 1)[1].split('run_frontend() {', 1)[0]
    frontend = source.split('run_frontend() {', 1)[1].split('run_smoke() {', 1)[0]

    assert '"$@" || status=$?' in timed
    assert 'return "$status"' in timed
    assert "printf '❌ %s · exit %d" in timed
    assert "printf '✅ %s · ⏱ %dm %02ds" in timed
    assert "run_timed_setup 'Functional npm dependencies' npm ci --no-audit --no-fund" in functional
    assert "run_timed_setup 'Functional CSS build' npm run build-css" in functional
    for label, command in (
        ('Frontend npm dependencies', 'npm ci --no-audit --no-fund'),
        ('Frontend format check', 'npm run check-format'),
        ('Frontend asset build', 'npm run build-frontend'),
        ('Frontend asset verification', 'npm run verify-frontend'),
    ):
        assert f"run_timed_setup '{label}' {command}" in frontend
    assert functional.index('Functional CSS build') < functional.index("'Functional Tests'")
    assert '--durations=15' in functional
    assert 'run_e2e_gate' in functional


def test_functional_full_suite_records_bounded_slowest_pytest_durations() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    functional = source.split('run_tests() {', 1)[1].split('run_frontend() {', 1)[0]

    assert 'run_pytest_capture \\' in functional
    assert "'Functional Tests'" in functional
    assert '--durations=15' in functional
    assert functional.count('--durations=15') == 1
    assert '--junitxml="$TEST_OUTPUT_DIR/release-suite.xml"' in functional
    assert "-m 'not debug and not e2e and not contract and not migration'" in functional
    assert 'run_e2e_gate' in functional
    assert 'render_test_taxonomy_summary' in functional
    assert 'pytest "$@" >"$log_file" 2>&1' in source


def test_taxonomy_summary_merges_split_junit_evidence_by_kaori_test_purpose(tmp_path: Path) -> None:
    release_junit = tmp_path / 'release-suite.xml'
    release_junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="5" failures="0" errors="0" skipped="0">
    <testcase classname="tests.unit.reports.test_unit" name="test_unit" />
    <testcase classname="tests.welcome.test_page" name="test_functional" />
    <testcase classname="tests.integration.kubernetes.test_repo" name="test_integration" />
    <testcase classname="tests.security.test_rbac" name="test_security" />
    <testcase classname="tests.rendering.test_template" name="test_rendering" />
  </testsuite>
</testsuites>
""",
        encoding='utf-8',
    )
    contract_junit = tmp_path / 'contract-migration.xml'
    contract_junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" failures="0" errors="0" skipped="0">
    <testcase classname="tests.contracts.release.test_contract" name="test_contract" />
    <testcase classname="tests.migrations.test_upgrade" name="test_migration" />
  </testsuite>
</testsuites>
""",
        encoding='utf-8',
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(CI_ADMISSION),
            'test-summary',
            '--junit',
            str(contract_junit),
            '--junit',
            str(release_junit),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    for expected in (
        '✅ Unit Tests · 1 test',
        '✅ Functional Tests · 1 test',
        '✅ Integration Tests · 1 test',
        '✅ Security Regression · 1 test',
        '✅ Rendering / UI · 1 test',
        '✅ Contract Tests · 1 test',
        '✅ Migration Tests · 1 test',
    ):
        assert expected in completed.stdout


def test_full_admission_aggregates_split_junit_artifacts_before_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    for token in (
        'Upload Static JUnit Evidence',
        'Upload Functional JUnit Evidence',
        'Download Static JUnit Evidence',
        'Download Functional JUnit Evidence',
        'Write Full Test Taxonomy Summary',
        'full-admission-junit-static-',
        'full-admission-junit-functional-',
        'admission-junit/static/contract-migration.xml',
        'admission-junit/functional/release-suite.xml',
        'admission-junit/functional/e2e.xml',
    ):
        assert token in workflow


def test_successful_functional_timing_artifact_is_bounded_and_does_not_replace_junit() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')
    timing = workflow.split('      - name: Upload Successful Functional Timing Report\n', 1)[1].split(
        '      - name: Upload Static Diagnostics\n', 1
    )[0]

    assert "if: ${{ success() && matrix.gate == 'functional' }}" in timing
    assert 'full-admission-functional-timing-${{ github.run_id }}-${{ github.run_attempt }}' in timing
    assert 'path: tmp/ci-artifacts/test-output/functional-tests.*.log' in timing
    assert 'path: tmp/ci-artifacts/test-output\n' not in timing
    assert 'if-no-files-found: error' in timing
    assert 'retention-days: 3' in timing
    assert 'Upload Functional JUnit Evidence' in workflow
    assert 'tmp/ci-artifacts/test-output/release-suite.xml' in workflow
    assert 'tmp/ci-artifacts/test-output/e2e.xml' in workflow
    failure_upload = workflow.split('      - name: Upload Test Diagnostics\n', 1)[1].split(
        '      - name: Upload Runtime Diagnostics\n', 1
    )[0]
    assert "if: ${{ failure() && matrix.gate == 'functional' }}" in failure_upload


def test_raw_ci_diagnostics_are_uploaded_as_artifacts() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'Upload Static Diagnostics' in workflow
    assert 'Upload Test Diagnostics' in workflow
    assert 'Upload Smoke Diagnostics' in workflow
    assert 'tmp/ci-artifacts/static-output' in workflow
    assert 'tmp/ci-artifacts/test-output' in workflow


def test_admission_summary_reports_real_failure_state_instead_of_hardcoded_pass() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'RESULT=' in workflow
    assert 'FIRST_FAILURE=' in workflow
    assert '--result "$RESULT"' in workflow
    assert '--first-failure "$FIRST_FAILURE"' in workflow
    assert '--result PASS' not in workflow
    assert "printf '✅ %s · ⏱ %s\\n'" in workflow
    assert "printf '❌ %s · ⏱ %s\\n'" in workflow
    assert "printf '📦 %s\\n'" in workflow
    assert "printf '➡️ %s\\n'" in workflow


def test_long_static_gate_has_non_blocking_periodic_heartbeat() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'Static & Governance still running' in workflow
    assert 'sleep 60' in workflow
    assert 'heartbeat_pid=$!' in workflow
    assert 'wait "$gate_pid" || gate_status=$?' in workflow
    assert 'kill "$heartbeat_pid" >/dev/null 2>&1 || true' in workflow
    assert 'wait "$heartbeat_pid" >/dev/null 2>&1 || true' in workflow
    assert 'exit "$gate_status"' in workflow
    assert '⏱ %dm %02ds' in workflow


def test_staging_deploy_action_uses_operator_facing_staging_host_vocabulary() -> None:
    workflow = STAGING_DEPLOY_WORKFLOW.read_text(encoding='utf-8')

    assert 'name: Staging Deploy' in workflow
    assert 'name: Release Evidence' in workflow
    assert 'name: Deploy Staging' in workflow
    assert 'description: Accepted KAORI RC tag' in workflow
    assert "printf 'Staging authority resolved:" in workflow
    assert 'KAORI UAT VPS Deploy' not in workflow
    assert 'Deploy Immutable Candidate to UAT VPS' not in workflow


def test_developer_check_publishes_only_executed_checks_and_selected_route() -> None:
    workflow = DEVELOPER_WORKFLOW.read_text(encoding='utf-8')

    assert 'Python & Governance — executed validation' in workflow
    assert 'Frontend & Focused Validation — executed validation' in workflow
    assert 'Developer Check — path-aware execution boundary' in workflow
    assert 'printf -v command_display' in workflow
    assert 'executed_checks=$((executed_checks + 1))' in workflow
    assert "|| status=$?" in workflow
    assert 'return "$status"' in workflow
    assert 'test_status=$?' in workflow
    assert 'exit "$test_status"' in workflow
    assert 'Unselected path-aware checks were NOT RUN.' in workflow
    assert 'Unselected checks were NOT RUN.' in workflow
    assert 'SKIPPED means not executed' in workflow
    assert 'GITHUB_STEP_SUMMARY' in workflow


def test_full_static_verifier_report_is_execution_based_and_reuses_existing_logs() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'verification-report.md' in source
    assert 'Every executed verifier is published as evidence' in source
    assert 'Registered capability evidence is a separate source-ownership inventory' in source
    assert 'Registered capability ownership (not executed tests)' in source
    assert 'sed -n \'/^  EVIDENCE REGISTERED ONLY/,$p\'' in source
    assert 'command_display="$3"' in source
    assert '"$group" "$label" "$command_display"' in source
    assert '$(basename "$log_file")' in source
    assert 'PASS | %dm %02ds' in source
    assert 'FAIL (exit %d)' in source
    assert 'run_contract_migration_gate' in source
    assert 'Publish Executed Gate Coverage' in workflow
    assert 'cat "$report" >> "$GITHUB_STEP_SUMMARY"' in workflow
    assert 'Upload Successful Static Verification Details' in workflow
    assert 'full-admission-static-verifiers-' in workflow
    assert 'if-no-files-found: error' in workflow
    assert 'Upload Static Diagnostics' in workflow


def test_full_admission_gate_summary_uses_real_step_outcomes() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    for step in (
        'static_gate', 'security_gate', 'functional_gate', 'frontend_gate',
        'runtime_build', 'runtime_scan', 'runtime_dast',
    ):
        assert f'id: {step}' in workflow
        assert f'steps.{step}.outcome' in workflow
    for marker in (
        'Tool chain: actionlint, zizmor, shellcheck, hadolint, gitleaks, Bandit, Semgrep, pip-audit (base/dev) and npm audit',
        'Only stages reached before the failure may have executed.',
        'Functional release suite and dedicated E2E suite',
        'Runtime and DAST results are deployment/security checks',
        'Upload Successful Security Scan Evidence',
        'full-admission-security-scans-',
    ):
        assert marker in workflow
    assert 'Publish Executed Gate Coverage' in workflow
    assert "if: ${{ always() }}" in workflow
