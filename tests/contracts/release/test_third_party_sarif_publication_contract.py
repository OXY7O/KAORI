"""Third-party Code Scanning reporting never widens KAORI's trusted CI boundary."""

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
