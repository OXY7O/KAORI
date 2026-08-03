from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.tls_certificate_health import (
    build_tls_certificate_health_presentation,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _record(
    *,
    cluster: str,
    namespace: str,
    secret: str,
    status: str,
    days: int,
    usage_state: str,
    coverage_state: str = 'fully_covered',
    parse_error: str = '',
) -> dict[str, object]:
    now = datetime(2026, 8, 3, 6, 0, tzinfo=UTC)
    status_labels = {
        'healthy': ('Valid', 'normal'),
        'warning': ('Renewal Window', 'warning'),
        'critical': ('Critical Expiry', 'critical'),
        'expired': ('Expired', 'critical'),
        'invalid': ('Invalid', 'critical'),
        'unknown': ('Unknown', 'muted'),
    }
    usage_labels = {
        'in_use': ('In Use', 'normal'),
        'unused': ('Unused', 'info'),
        'unknown_usage': ('Unknown Usage', 'warning'),
    }
    coverage_labels = {
        'fully_covered': ('Fully Covered', 'normal'),
        'partial': ('Partial Coverage', 'warning'),
        'uncovered': ('Uncovered', 'critical'),
        'no_declared_hosts': ('No Declared Hosts', 'info'),
        'not_reported': ('Not Reported', 'muted'),
    }
    status_label, status_tone = status_labels[status]
    usage_label, usage_tone = usage_labels[usage_state]
    coverage_label, coverage_tone = coverage_labels[coverage_state]
    in_use = usage_state == 'in_use'
    return {
        'cluster': cluster,
        'namespace': namespace,
        'secret_name': secret,
        'secret_identity': f'{namespace}/{secret}',
        'common_name': f'{secret}.example.internal',
        'issuer': 'Example Internal CA',
        'fingerprint_short': '1234567890abcdef',
        'dns_names_label': f'{secret}.example.internal',
        'ingress_hosts_label': f'{secret}.example.internal' if in_use else 'Not Available',
        'references_label': f'{namespace}/{secret}-ingress' if in_use else (
            'No committed reference' if usage_state == 'unused' else 'Not Available'
        ),
        'reference_count': 1 if in_use else 0,
        'usage_state': usage_state,
        'usage_label': usage_label,
        'usage_tone': usage_tone,
        'not_before': now - timedelta(days=90),
        'not_after': now + timedelta(days=days),
        'days_remaining': days,
        'status': status,
        'status_label': status_label,
        'status_tone': status_tone,
        'parse_error': parse_error,
        'parse_state': 'Failed' if parse_error else 'Passed',
        'parse_tone': 'critical' if parse_error else 'normal',
        'coverage_state': coverage_state,
        'coverage_label': coverage_label,
        'coverage_tone': coverage_tone,
        'declared_host_count': 1 if in_use else 0,
        'covered_host_count': 0 if coverage_state in {'partial', 'uncovered'} else (1 if in_use else 0),
        'uncovered_hosts_label': f'{secret}.example.internal' if coverage_state in {'partial', 'uncovered'} else 'None',
        'collected_at': now,
        'key_pair_state': 'Not Collected',
        'chain_state': 'Not Collected',
    }


def _payload() -> dict[str, object]:
    records = [
        _record(cluster='K8s Staging', namespace='portal', secret='portal-tls', status='healthy', days=83, usage_state='in_use'),
        _record(cluster='K8s Staging', namespace='api', secret='api-tls', status='warning', days=24, usage_state='in_use'),
        _record(cluster='K8s Staging', namespace='payment', secret='payment-tls', status='critical', days=6, usage_state='in_use'),
        _record(cluster='K8s Dev', namespace='legacy', secret='legacy-tls', status='expired', days=-12, usage_state='in_use'),
        _record(cluster='K8s Staging', namespace='shared', secret='unused-wildcard', status='healthy', days=145, usage_state='unused'),
        _record(cluster='K8s Dev', namespace='gateway', secret='gateway-tls', status='invalid', days=0, usage_state='unknown_usage', coverage_state='not_reported', parse_error='Secret is missing tls.crt.'),
        _record(cluster='K8s Staging', namespace='shop', secret='shop-tls', status='healthy', days=95, usage_state='in_use', coverage_state='uncovered'),
    ]
    return {
        'cluster': {'environment': '2 Environments'},
        'records': records,
        'summary': {
            'total': 7,
            'healthy': 3,
            'warning': 1,
            'critical': 1,
            'expired': 1,
            'invalid': 1,
            'unknown': 0,
            'in_use': 5,
            'unused': 1,
            'unknown_usage': 1,
            'fully_covered': 4,
            'partial': 0,
            'uncovered': 1,
            'no_declared_hosts': 1,
            'not_reported': 1,
            'issuer_count': 1,
            'expired_in_use': 1,
            'critical_in_use': 1,
            'warning_in_use': 1,
            'invalid_in_use': 0,
            'uncovered_in_use': 1,
            'action_required': 3,
            'renewal_attention': 1,
            'cluster_count': 2,
            'secret_collection_exceptions': 0,
            'ingress_mapping_exceptions': 1,
            'collection_exceptions': 1,
            'missing_secret_count': None,
            'missing_secret_evidence': 'Not Collected',
        },
        'source_evidence': [
            {
                'cluster': 'K8s Staging',
                'secret_collection_status': 'collected',
                'ingress_mapping_status': 'collected',
                'collected_at': datetime(2026, 8, 3, 6, 0, tzinfo=UTC),
            },
            {
                'cluster': 'K8s Dev',
                'secret_collection_status': 'collected',
                'ingress_mapping_status': 'permission_unavailable',
                'collected_at': datetime(2026, 8, 3, 5, 55, tzinfo=UTC),
            },
        ],
        'validity_policy': {'renewal_window_days': 30, 'critical_window_days': 7},
        'schema_readiness': {'ready': True, 'database_reachable': True},
        'sensitive_data_policy': {
            'private_key_collected': False,
            'secret_values_collected': False,
            'pair_validation_state': 'Not Collected',
            'chain_validation_state': 'Not Collected',
        },
    }


def _presentation() -> dict[str, object]:
    return build_tls_certificate_health_presentation(
        SimpleNamespace(report_type='tls_certificate_health'),
        _payload(),
        report_id='811',
        report_name='TLS Certificate Health Validation',
        cluster_scope='All Clusters',
        namespace_scope='All Namespaces',
        period_label='Current Inventory Snapshot',
        data_cutoff='03 Aug 2026 06:00 UTC',
        generated_at='03 Aug 2026 06:10 UTC',
        generated_by='Platform Operations',
        classification='Internal',
    )


def _rendered_html() -> str:
    environment = Environment(
        loader=FileSystemLoader(PROJECT_ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    document = SimpleNamespace(
        report_name='TLS Certificate Health Validation',
        presentation=_presentation(),
    )
    return environment.get_template('reports/pdf/tls_certificate_health.html').render(document=document)


def test_tls_publication_uses_fixed_nine_page_contract() -> None:
    presentation = _presentation()

    assert presentation['page_count'] == 9
    assert presentation['layout_contract']['paper'] == 'A4 Portrait'
    assert presentation['layout_contract']['source_policy'] == 'committed-db-snapshot-only'
    assert presentation['layout_contract']['private_key_policy'] == 'never-collected-or-rendered'


def test_tls_usage_and_validity_are_separate_dimensions() -> None:
    presentation = _presentation()
    rows = presentation['validity']['rows']

    expired = next(item for item in rows if item['secret'] == 'legacy-tls')
    unused = next(item for item in rows if item['secret'] == 'unused-wildcard')

    assert expired['usage'] == 'In Use'
    assert expired['status'] == 'Expired'
    assert unused['usage'] == 'Unused'
    assert unused['status'] == 'Valid'


def test_tls_private_key_material_is_never_rendered() -> None:
    html = _rendered_html()

    assert 'Private-key material is excluded by design.' in html
    assert 'Not Collected' in html
    assert 'tls.key values' in html
    assert 'BEGIN PRIVATE KEY' not in html
    assert 'secret_values' not in html


def test_tls_methodology_keeps_boundary_columns_side_by_side() -> None:
    html = _rendered_html()
    css = (PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'tls_certificate_health.css').read_text(
        encoding='utf-8'
    )

    assert 'class="boundary-columns"' in html
    assert 'Included in This Report' in html
    assert 'Not Included in This Report' in html
    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)' in css
    assert 'column-gap: 14mm' in css


def test_tls_renderer_and_system_template_are_registered() -> None:
    engine = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text(encoding='utf-8')
    builder = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'builder.py').read_text(encoding='utf-8')
    templates = (PROJECT_ROOT / 'app' / 'reports' / 'report_templates' / 'service.py').read_text(encoding='utf-8')
    generator = (PROJECT_ROOT / 'app' / 'reports' / 'generate' / 'service.py').read_text(encoding='utf-8')

    assert "'reports/pdf/tls_certificate_health.html': 'tls_certificate_health.css'" in engine
    assert 'build_tls_certificate_health_presentation' in builder
    assert "'id': 'tls_certificate_health'" in templates
    assert "'family': 'governance'" in generator


def test_tls_publication_renders_exactly_nine_a4_pages(tmp_path: Path) -> None:
    output_path = tmp_path / 'tls_certificate_health.pdf'
    font_config = FontConfiguration()
    HTML(string=_rendered_html(), base_url=str(PROJECT_ROOT)).write_pdf(
        target=str(output_path),
        stylesheets=[
            CSS(
                filename=str(PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'tls_certificate_health.css'),
                font_config=font_config,
            ),
            CSS(
                filename=str(PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'kaori_publication.css'),
                font_config=font_config,
            ),
        ],
        font_config=font_config,
        presentational_hints=True,
    )

    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 9
    for page in reader.pages:
        assert 594 <= float(page.mediabox.width) <= 596
        assert 841 <= float(page.mediabox.height) <= 843
