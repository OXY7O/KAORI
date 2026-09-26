import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
WORKFLOW = ROOT / '.github/workflows/quality.yml'
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


def test_failed_static_verifier_remains_failure_first_and_names_the_check() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'printf \'❌ %s\\n\' "$label"' in source
    assert '❌ First actionable failure' in source
    assert '📦 Diagnostic excerpt' in source
    assert '➡️ Repair %s, collect remaining findings' in source


def test_release_suite_emits_junit_for_taxonomy_summary_without_duplicate_execution() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert '--junitxml="$TEST_OUTPUT_DIR/release-suite.xml"' in source
    assert '--junitxml="$TEST_OUTPUT_DIR/e2e.xml"' in source
    assert '--junitxml="$TEST_OUTPUT_DIR/contract-migration.xml"' in source
    assert 'ci_admission.py test-summary' in source
    assert 'render_contract_migration_taxonomy_summary' in source
    assert "-m 'not debug and not e2e and not contract and not migration'" in source
    assert 'Domain Characterization Tests' not in source


def test_taxonomy_summary_groups_existing_junit_by_kaori_test_purpose(tmp_path: Path) -> None:
    junit = tmp_path / 'release-suite.xml'
    junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="7" failures="0" errors="0" skipped="0">
    <testcase classname="tests.unit.reports.test_unit" name="test_unit" />
    <testcase classname="tests.welcome.test_page" name="test_functional" />
    <testcase classname="tests.integration.kubernetes.test_repo" name="test_integration" />
    <testcase classname="tests.security.test_rbac" name="test_security" />
    <testcase classname="tests.rendering.test_template" name="test_rendering" />
    <testcase classname="tests.contracts.release.test_contract" name="test_contract" />
    <testcase classname="tests.migrations.test_upgrade" name="test_migration" />
  </testsuite>
</testsuites>
""",
        encoding='utf-8',
    )

    completed = subprocess.run(
        [sys.executable, str(CI_ADMISSION), 'test-summary', '--junit', str(junit)],
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


def test_long_static_gate_has_periodic_heartbeat() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'Static & Governance still running' in workflow
    assert 'sleep 60' in workflow
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
