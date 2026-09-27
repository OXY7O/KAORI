from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_governance_report_is_registered_in_canonical_catalog() -> None:
    catalog = (ROOT / 'app/definitions/catalogs/reports/catalog.yaml').read_text(encoding='utf-8')
    reference = (ROOT / 'app/reports/reference.py').read_text(encoding='utf-8')

    assert 'value: tenant_governance' in catalog
    assert 'family: analytics' in catalog
    assert 'default_format: pdf' in catalog
    assert "'tenant_governance': 'TNG'" in reference


def test_all_formats_share_one_canonical_tenant_payload() -> None:
    collectors = (ROOT / 'app/reports/export/html_pdf/collectors.py').read_text(encoding='utf-8')
    csv_renderer = (ROOT / 'app/reports/export/csv/renderer.py').read_text(encoding='utf-8')
    xlsx_renderer = (ROOT / 'app/reports/export/xlsx/renderer.py').read_text(encoding='utf-8')

    assert "'tenant_governance': get_report_tenant_governance_payload" in collectors
    assert 'collect_report_payload(report)' in csv_renderer
    assert 'collect_report_payload(report)' in xlsx_renderer


def test_tenant_report_consumes_committed_state_and_canonical_intelligence() -> None:
    payload = (ROOT / 'app/reports/export/payloads/tenant_governance.py').read_text(encoding='utf-8')

    assert 'get_active_recommendation_findings' in payload
    assert "domain='kubernetes'" in payload
    assert "startswith('kubernetes.tenant.')" in payload
    assert 'runtime_adapter' not in payload
    assert 'requests.' not in payload


def test_tenant_report_never_exports_credential_secret_material() -> None:
    payload = (ROOT / 'app/reports/export/payloads/tenant_governance.py').read_text(encoding='utf-8')

    forbidden = (
        'token_material',
        'kubeconfig_content',
        'private_key',
        'secret_data',
        'generation.material',
    )
    for marker in forbidden:
        assert marker not in payload
    assert "'secret_material_persisted': False" in payload


def test_tenant_pdf_uses_report_document_not_dashboard_capture() -> None:
    builder = (ROOT / 'app/reports/export/html_pdf/builder.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/reports/pdf/tenant_governance.html').read_text(encoding='utf-8')

    assert "report.report_type == 'tenant_governance'" in builder
    assert "template_name = 'reports/pdf/tenant_governance.html'" in builder
    assert 'document.sections' in template
    assert 'screenshot' not in template.lower()


def test_tenant_xlsx_profile_has_governance_evidence_sheets() -> None:
    profile = (ROOT / 'app/reports/export/xlsx/analytics_profile_catalog.py').read_text(encoding='utf-8')
    preparer = (
        ROOT / 'app/reports/export/xlsx/analytics_preparation/tenant_governance.py'
    ).read_text(encoding='utf-8')

    assert "'tenant_governance': AnalyticsWorkbookProfile(" in profile
    for sheet in ('Tenants', 'Namespaces', 'Access', 'Credentials', 'Allocations', 'Governance'):
        assert f"'{sheet}'" in profile
        assert f"'{sheet}'" in preparer
