from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_registered_tenant_audit_domain_has_operator_coverage_and_exclusion() -> None:
    registry = (ROOT / 'app/platform_operations/data_lifecycle/retention/domains/__init__.py').read_text(
        encoding='utf-8'
    )
    presentation = (ROOT / 'app/platform_operations/data_lifecycle/retention/presentation.py').read_text(
        encoding='utf-8'
    )
    coverage = (ROOT / 'app/platform_operations/data_lifecycle/retention/domain_coverage.py').read_text(
        encoding='utf-8'
    )
    assert "'tenant_audit_evidence': TenantAuditEvidenceArchiveDomain" in registry
    assert 'from app.platform_operations.data_lifecycle.retention.domain_coverage import _domain_coverage' in presentation
    assert '_domain_coverage(name)' in presentation
    for value in (
        "'tenant_audit_evidence': 'Tenant Audit Evidence'",
        "'tenant_audit_evidence': 'shield-check'",
        'Raw Kubernetes audit logs and provider request/response bodies',
    ):
        assert value in presentation
    for value in (
        "'tenant_audit_evidence': (",
        "'label': 'Tenant Audit Correlation'",
        "'label': 'Identity & Outcome Evidence'",
    ):
        assert value in coverage


def test_current_docs_reconcile_nine_adapters_without_rewriting_lock() -> None:
    root = ROOT / 'app/platform_operations/data_lifecycle'
    foundation = (root / 'retention/README.md').read_text(encoding='utf-8')
    workspace = (root / 'README.md').read_text(encoding='utf-8')
    for key in ('alert_incident', 'tenant_audit_evidence'):
        assert key in foundation
        assert key in workspace
    assert 'nine' in foundation.lower()
    assert 'audit_event' in foundation
    assert 'notification_delivery' in foundation
    assert 'v1.3' in foundation
    assert 'raw provider audit logs' in workspace
