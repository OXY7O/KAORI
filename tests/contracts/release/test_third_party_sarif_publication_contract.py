"""Third-party Code Scanning reporting never widens KAORI's trusted CI boundary."""

import json
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


def test_native_bandit_sarif_publisher_pins_optional_formatter() -> None:
    requirements = SECURITY_REQUIREMENTS.read_text(encoding='utf-8')
    original_gate = SECURITY_GATE.read_text(encoding='utf-8')
    source = WORKFLOW.read_text(encoding='utf-8')

    assert 'bandit[sarif]==1.9.4' in requirements
    assert 'jschema-to-python==1.2.3' in requirements
    assert 'sarif-om==1.0.4' in requirements
    assert 'bandit -r app scripts -q -ll -f json' in original_gate
    assert 'bandit -r app scripts -q -ll -f sarif' in source
    assert 'bandit -r app scripts -q -ll -f sarif' not in original_gate
    assert '-o tmp/ci-artifacts/security/bandit.sarif' in source


def test_bandit_native_sarif_uses_own_category_and_strict_upload_gate() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')
    assert 'name: SAST Code Scanning' in source
    assert 'id: bandit_scan' in source
    assert 'id: bandit_report' in source
    assert 'id: bandit_upload' in source
    assert 'category: kaori-sast-bandit' in source
    assert 'category: kaori-sast-semgrep' in source
    assert '(.runs[0].tool.driver.name | ascii_downcase == "bandit")' in source
    assert 'BANDIT_SCAN_OUTCOME: ${{ steps.bandit_scan.outcome }}' in source
    assert 'BANDIT_REPORT_OUTCOME: ${{ steps.bandit_report.outcome }}' in source
    assert 'BANDIT_UPLOAD_OUTCOME: ${{ steps.bandit_upload.outcome }}' in source
    assert '"$BANDIT_SCAN_OUTCOME" == success' in source
    assert '"$BANDIT_REPORT_OUTCOME" == success' in source
    assert '"$BANDIT_UPLOAD_OUTCOME" == success' in source
    assert source.count('wait-for-processing: true') == 2
    assert source.count('github/codeql-action/upload-sarif@') == 2
    assert 'pull_request_target' not in source


def test_bandit_formatter_generates_native_sarif_from_synthetic_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / 'no-findings.py'
    report = tmp_path / 'bandit.sarif'
    source.write_text('def safe_answer() -> int:\n    return 42\n', encoding='utf-8')

    completed = subprocess.run(
        ['bandit', '-q', '-ll', '-f', 'sarif', '-o', str(report), str(source)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(report.read_text(encoding='utf-8'))
    assert payload['version'] == '2.1.0'
    assert len(payload['runs']) == 1
    assert payload['runs'][0]['tool']['driver']['name'] == 'Bandit'
    assert payload['runs'][0].get('results', []) == []
