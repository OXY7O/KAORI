from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SECURITY_REQUIREMENTS = ROOT / '.github' / 'ci' / 'requirements-security.txt'
SECURITY_RUNNER = ROOT / '.github' / 'ci' / 'run-security-static.sh'
URLLIB_SUPPRESSION_OWNERS = (
    ROOT / 'scripts' / 'ci_delivery_context.py',
    ROOT / 'scripts' / 'ci_delivery_notify.py',
)


def test_bandit_b310_suppressions_keep_explanatory_prose_outside_directive() -> None:
    for path in URLLIB_SUPPRESSION_OWNERS:
        source = path.read_text(encoding='utf-8')
        assert '# nosec B310' in source
        assert '# nosec B310 -' not in source


def test_semgrep_security_toolchain_uses_reviewed_current_pin() -> None:
    requirements = SECURITY_REQUIREMENTS.read_text(encoding='utf-8').splitlines()

    assert 'semgrep==1.177.0' in requirements
    assert 'semgrep==1.174.0' not in requirements


def test_sast_noise_cleanup_preserves_security_gate_strictness() -> None:
    runner = SECURITY_RUNNER.read_text(encoding='utf-8')

    assert 'bandit -r app scripts -q -ll' in runner
    assert 'semgrep scan' in runner
    assert '--error' in runner
    assert '--config .github/ci/semgrep.yml' in runner
    assert 'app scripts frontend' in runner


def test_semgrep_sarif_reuses_the_existing_sast_scan() -> None:
    runner = SECURITY_RUNNER.read_text(encoding='utf-8')

    assert runner.count('semgrep scan') == 1
    assert '--json-output "$ARTIFACT_DIR/semgrep.json"' in runner
    assert '--sarif-output "$ARTIFACT_DIR/semgrep.sarif"' in runner
    assert '--error' in runner
    assert 'bandit -r app scripts -q -ll' in runner


def test_code_scanning_upload_is_only_for_trusted_pushes() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'quality.yml').read_text(
        encoding='utf-8'
    )
    reporter = workflow.split('  semgrep-code-scanning:\n', 1)[1].split(
        '  integration-smoke:\n', 1
    )[0]

    assert 'github.event_name == \'push\'' in reporter
    assert "github.ref == 'refs/heads/kaori/staging'" in reporter
    assert "github.ref == 'refs/heads/main'" in reporter
    assert 'needs: [validation-profile, full-admission-gates]' in reporter
    assert 'runs-on: ubuntu-24.04' in reporter
    assert 'security-events: write' in reporter
    assert 'contents: read' in reporter
    assert 'actions: read' in reporter
    assert 'SCANNED_SHA' in reporter and 'PUSH_SHA' in reporter
    assert 'persist-credentials: false' in reporter
    assert 'kaori-semgrep-sast-' in reporter
    assert 'category: kaori-semgrep-sast' in reporter
    assert 'github/codeql-action/upload-sarif@cdf488f595d80d6e07e03d4674febd5ab45fa938' in reporter
    assert 'pull_request_target' not in workflow

    scan_artifact = workflow.split(
        '      - name: Retain Semgrep SARIF for trusted branch code scanning\n', 1
    )[1].split('      - name: Upload Successful Static Verification Details\n', 1)[0]
    assert 'matrix.gate == \'security\'' in scan_artifact
    assert "github.event_name == 'push'" in scan_artifact
    assert 'tmp/ci-artifacts/security/semgrep.sarif' in scan_artifact


def test_reusable_sarif_permission_is_not_granted_to_untrusted_forks() -> None:
    caller = (ROOT / '.github' / 'workflows' / 'developer-check.yml').read_text(
        encoding='utf-8'
    )
    route = caller.split('  full-admission:\n', 1)[1].split(
        '  ready-admission-guard:\n', 1
    )[0]

    assert "github.event.pull_request.draft == false" in route
    assert "github.event.pull_request.head.repo.full_name == github.repository" in route
    assert "startsWith(github.event.pull_request.head.ref, 'kaori/')" in route
    assert 'permissions:\n      contents: read\n      actions: read' in route
    assert '      security-events: write\n    uses: ./.github/workflows/quality.yml' in route
    # No global write grant: the untrusted fork jobs inherit read-only access.
    header = caller.split('jobs:\n', 1)[0]
    assert 'security-events: write' not in header
