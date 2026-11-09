"""Third-party Code Scanning reporting never widens KAORI's trusted CI boundary."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github/workflows/security-findings-publish.yml'
SECURITY_GATE = ROOT / '.github/ci/run-security-static.sh'
SECURITY_REQUIREMENTS = ROOT / '.github/ci/requirements-security.txt'
REPORTING_DOC = ROOT / 'docs/security/THIRD_PARTY_CODE_SCANNING_REPORTING.md'


def test_semgrep_reporting_uses_existing_rulebook_and_canonical_toolchain() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')
    security_gate = SECURITY_GATE.read_text(encoding='utf-8')
    requirements = SECURITY_REQUIREMENTS.read_text(encoding='utf-8')

    assert 'semgrep==1.177.0' in requirements
    assert '--config .github/ci/semgrep.yml' in security_gate
    assert '--config .github/ci/semgrep.yml' in source
    assert '--error --metrics=off' in source
    assert '--exclude node_modules' in source
    assert '--exclude app/static/vendor' in source
    assert 'app scripts frontend' in source
    assert '--sarif-output tmp/ci-artifacts/security/semgrep.sarif' in source
    assert 'context: .' in source
    assert 'file: .github/ci/Dockerfile' in source
    assert 'target: ci' in source
    assert 'cache-from: type=gha,scope=kaori-ci-toolchain-v1' in source
    assert 'ref: ${{ github.sha }}' in source


def test_sarif_publisher_only_triggers_on_trusted_protected_pushes() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')
    assert '  push:' in source
    assert '      - kaori/staging' in source
    assert '      - main' in source
    for invalid_trigger in ('  pull_request:', '  pull_request_target:', '  workflow_run:'):
        assert invalid_trigger not in source
    assert "github.event_name == 'push'" in source
    assert "github.ref == 'refs/heads/kaori/staging'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert '    permissions:\n      contents: read\n      security-events: write' in source
    assert '    timeout-minutes: 45' in source
    assert 'persist-credentials: false' in source


def test_sarif_upload_preserves_failed_scan_gate_and_excludes_secret_payloads() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')
    assert 'github/codeql-action/upload-sarif@33d7b85da1a04171e211befe2c739303b9a4c066' in source
    assert 'category: kaori-sast-semgrep' in source
    assert 'wait-for-processing: true' in source
    assert '($tool == "semgrep" or $tool == "semgrep oss" or' in source
    assert '$tool == "semgrep community edition")' in source
    assert 'SCAN_OUTCOME: ${{ steps.scan.outcome }}' in source
    assert 'REPORT_OUTCOME: ${{ steps.report.outcome }}' in source
    assert 'UPLOAD_OUTCOME: ${{ steps.upload.outcome }}' in source
    assert '[[ "$SCAN_OUTCOME" == success && "$REPORT_OUTCOME" == success && "$UPLOAD_OUTCOME" == success ]]' in source
    assert 'gitleaks' not in source.lower()
    assert 'zap' not in source.lower()
    assert 'pull_request_target' not in source


def test_dast_publication_requires_truthful_locations_and_privacy_review() -> None:
    documentation = REPORTING_DOC.read_text(encoding='utf-8')
    assert '#4390' in documentation
    assert '#4391' in documentation
    assert '#4388' in documentation
    assert 'No `pull_request_target`' in documentation or '`pull_request_target`' in documentation
    assert 'cookies' in documentation.lower()
    assert 'response bodies' in documentation.lower()
    assert 'source path' in documentation.lower()
    assert 'NOT VERIFIED' in documentation
    assert 'Gitleaks' in documentation
    assert 'CodeQL Default Setup' in documentation


def test_bandit_reporter_preserves_pinned_policy_and_least_privilege() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')
    requirements = SECURITY_REQUIREMENTS.read_text(encoding='utf-8')
    mandatory_gate = SECURITY_GATE.read_text(encoding='utf-8')

    assert 'bandit[sarif]==1.9.4' in requirements
    assert 'sarif-om==1.0.4' in requirements
    assert 'jschema-to-python==1.2.3' in requirements
    assert 'bandit -r app scripts -q -ll -f json' in mandatory_gate
    assert '  bandit-code-scanning:' in source
    bandit_job = source.split('\n  bandit-code-scanning:', 1)[1]
    assert "github.event_name == 'push'" in bandit_job
    assert "github.ref == 'refs/heads/kaori/staging'" in bandit_job
    assert "github.ref == 'refs/heads/main'" in bandit_job
    assert '    permissions:\n      contents: read\n      security-events: write' in bandit_job
    assert 'ref: ${{ github.sha }}' in bandit_job
    assert 'persist-credentials: false' in bandit_job
    assert 'target: ci' in bandit_job
    assert 'bandit -r app scripts -q -ll -f sarif' in bandit_job
    assert 'category: kaori-sast-bandit' in bandit_job
    assert 'github/codeql-action/upload-sarif@33d7b85da1a04171e211befe2c739303b9a4c066' in bandit_job
    assert 'wait-for-processing: true' in bandit_job
    assert (
        '[[ "$SCAN_OUTCOME" == success && "$REPORT_OUTCOME" == success && "$UPLOAD_OUTCOME" == success ]]' in bandit_job
    )
    assert 'continue-on-error: true' in bandit_job
    assert 'pull_request_target' not in source
    assert 'gitleaks' not in source.lower()
    assert 'zap' not in source.lower()


def test_bandit_native_sarif_formatter_produces_real_source_locations(tmp_path: Path) -> None:
    """Synthetic issue validates the real pinned formatter without publishing a vulnerability."""
    binary = shutil.which('bandit')
    assert binary is not None, 'KAORI canonical CI toolchain must include Bandit.'
    fixture = tmp_path / 'bandit_fixture.py'
    fixture.write_text(
        'import subprocess\n\ndef unsafe(user_input):\n    subprocess.Popen("echo " + user_input, shell=True)\n',
        encoding='utf-8',
    )
    report = tmp_path / 'bandit.sarif'
    result = subprocess.run(
        [binary, '-r', str(fixture), '-q', '-ll', '-f', 'sarif', '-o', str(report)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(report.read_text(encoding='utf-8'))
    assert payload['version'] == '2.1.0'
    assert len(payload['runs']) == 1
    run = payload['runs'][0]
    assert run['tool']['driver']['name'] == 'Bandit'
    assert run['results'], 'A synthetic shell-injection fixture must produce SARIF findings.'
    assert all(
        finding['locations'][0]['physicalLocation']['artifactLocation']['uri'].endswith('bandit_fixture.py')
        and finding['locations'][0]['physicalLocation']['region']['startLine'] >= 1
        for finding in run['results']
    )
