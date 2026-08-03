from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.inventory_publications import (
    build_inventory_publication_presentation,
    inventory_template_for_report_type,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_TYPES = (
    'inventory_overview',
    'node_inventory',
    'namespace_inventory',
    'workload_inventory',
    'pod_inventory',
    'service_inventory',
    'ingress_inventory',
    'storage_inventory',
    'topology_inventory',
)


def _overview_payload() -> dict[str, object]:
    overview = {
        'clusters': 1,
        'nodes': 4,
        'ready_nodes': 4,
        'not_ready_nodes': 0,
        'node_readiness_percent': 100.0,
        'namespaces': 30,
        'workloads': 131,
        'pods': 196,
        'services': 126,
        'ingresses': 52,
        'configuration': 606,
        'storage': 33,
    }
    assets = [
        {'resource_type': label, 'assets': overview[key], 'status': 'Current'}
        for key, label in (
            ('clusters', 'Clusters'),
            ('nodes', 'Nodes'),
            ('namespaces', 'Namespaces'),
            ('workloads', 'Workloads'),
            ('pods', 'Pods'),
            ('services', 'Services'),
            ('ingresses', 'Ingresses'),
            ('configuration', 'Configuration'),
            ('storage', 'Storage'),
        )
    ]
    return {
        'cluster': {'environment': 'Staging'},
        'inventory_summary': {
            'total_assets': sum(item['assets'] for item in assets),
            'cluster_scope': 1,
            'namespace_scope': 30,
            'distinct_statuses': 1,
            'distinct_types': len(assets),
            'collected_at': '02 Aug 2026 14:33 UTC',
        },
        'inventory_overview': overview,
        'inventory_assets': assets,
        'inventory_distribution': {
            'by_cluster': [{'cluster': 'K8s PGN Staging', 'assets': sum(item['assets'] for item in assets)}],
            'by_status': [{'status': 'Current', 'assets': sum(item['assets'] for item in assets)}],
            'by_type': assets,
        },
        'topology_edges': [
            {'relationship': 'Namespace -> Workload', 'scope': 'All Namespaces', 'edges': 131, 'status': 'Committed'},
            {'relationship': 'Namespace -> Pod', 'scope': 'All Namespaces', 'edges': 196, 'status': 'Committed'},
            {'relationship': 'Pod -> Node', 'scope': 'K8s PGN Staging', 'edges': 196, 'status': 'Committed'},
            {'relationship': 'Ingress -> Service Backend', 'scope': 'All Namespaces', 'edges': 52, 'status': 'Committed'},
        ],
        'collected_at': '02 Aug 2026 14:33 UTC',
    }


def _asset_rows(report_type: str) -> list[dict[str, object]]:
    rows: dict[str, list[dict[str, object]]] = {
        'node_inventory': [
            {
                'node': 'k8s-worker-staging-001',
                'name': 'k8s-worker-staging-001',
                'role': 'Worker',
                'resource_type': 'Worker',
                'status': 'Ready',
                'unschedulable': 'Schedulable',
                'cpu': 8,
                'memory': '32 GiB',
                'kubelet_version': 'v1.29.5',
                'container_runtime': 'containerd://1.7.12',
                'memory_pressure': 'False',
                'disk_pressure': 'False',
                'internal_ip': '10.10.10.11',
            }
        ],
        'namespace_inventory': [
            {
                'namespace': 'monitoring',
                'name': 'monitoring',
                'resource_type': 'Namespace',
                'status': 'Active',
                'labels': 4,
                'annotations': 2,
                'limit_ranges': 1,
                'network_policies': 3,
                'service_accounts': 8,
                'default_service_account': 'Yes',
            }
        ],
        'workload_inventory': [
            {
                'name': 'prometheus',
                'namespace': 'monitoring',
                'resource_type': 'StatefulSet',
                'ready': '1/1',
                'status': 'Ready',
                'update_strategy': 'RollingUpdate',
                'desired_replicas': '1',
                'available_replicas': '1',
                'updated_replicas': '1',
            }
        ],
        'pod_inventory': [
            {
                'pod': 'prometheus-0',
                'name': 'prometheus-0',
                'namespace': 'monitoring',
                'resource_type': 'StatefulSet',
                'status': 'Running',
                'ready': '2/2',
                'node': 'k8s-worker-staging-001',
                'restarts': 0,
                'workload': 'prometheus',
                'container_count': 2,
                'image_count': 2,
                'persistent_volume_claims': 1,
            }
        ],
        'service_inventory': [
            {
                'name': 'prometheus-operated',
                'namespace': 'monitoring',
                'resource_type': 'ClusterIP',
                'status': 'Discovered',
                'cluster_ip': 'None',
                'external_ip': 'Not Available',
                'ports': '9090/TCP',
                'selector_count': 2,
                'selector': 'app=prometheus, operated=true',
                'load_balancer': 'Not Available',
            }
        ],
        'ingress_inventory': [
            {
                'name': 'grafana',
                'namespace': 'monitoring',
                'resource_type': 'nginx',
                'ingress_class': 'nginx',
                'status': 'TLS Enabled',
                'host': 'grafana.staging.example.internal',
                'address': '10.10.20.15',
                'backend_count': 1,
                'tls_secret_count': 1,
            }
        ],
        'storage_inventory': [
            {
                'name': 'pvc-prometheus-0',
                'namespace': 'monitoring',
                'resource_type': 'PersistentVolumeClaim',
                'status': 'Bound',
                'storage_class': 'cstor-csi-disk',
                'capacity': '100 GiB',
                'access_modes': 'ReadWriteOnce',
                'reclaim_policy': 'Delete',
                'claim_name': 'prometheus-db-prometheus-0',
                'provisioner': 'cstor.csi.openebs.io',
            }
        ],
    }
    return rows[report_type]


def _payload(report_type: str) -> dict[str, object]:
    if report_type in {'inventory_overview', 'topology_inventory'}:
        return _overview_payload()
    rows = _asset_rows(report_type)
    statuses: dict[str, int] = {}
    types: dict[str, int] = {}
    for row in rows:
        status = str(row.get('status') or 'Unknown')
        resource_type = str(row.get('resource_type') or 'Unknown')
        statuses[status] = statuses.get(status, 0) + 1
        types[resource_type] = types.get(resource_type, 0) + 1
    return {
        'cluster': {'environment': 'Staging'},
        'inventory_summary': {
            'total_assets': len(rows),
            'cluster_scope': 1,
            'namespace_scope': 1,
            'distinct_statuses': len(statuses),
            'distinct_types': len(types),
            'collected_at': '02 Aug 2026 14:33 UTC',
        },
        'inventory_assets': rows,
        'inventory_distribution': {
            'by_cluster': [{'cluster': 'K8s PGN Staging', 'assets': len(rows)}],
            'by_status': [{'status': label, 'assets': count} for label, count in statuses.items()],
            'by_type': [{'resource_type': label, 'assets': count} for label, count in types.items()],
        },
        'topology_edges': [
            {'relationship': 'Namespace -> Workload', 'scope': 'monitoring', 'edges': 1, 'status': 'Committed'},
            {'relationship': 'Workload -> Pod', 'scope': 'prometheus', 'edges': 1, 'status': 'Committed'},
            {'relationship': 'Pod -> Node', 'scope': 'k8s-worker-staging-001', 'edges': 1, 'status': 'Committed'},
            {'relationship': 'Service -> Selector', 'scope': 'monitoring', 'edges': 1, 'status': 'Committed'},
            {'relationship': 'Ingress -> Service Backend', 'scope': 'monitoring', 'edges': 1, 'status': 'Committed'},
            {'relationship': 'Namespace -> Storage', 'scope': 'monitoring', 'edges': 1, 'status': 'Committed'},
        ],
        'collected_at': '02 Aug 2026 14:33 UTC',
    }


def _presentation(report_type: str) -> dict[str, object]:
    return build_inventory_publication_presentation(
        SimpleNamespace(report_type=report_type),
        _payload(report_type),
        report_id='701',
        report_name='Inventory Validation',
        cluster_scope='K8s PGN Staging',
        namespace_scope='All Namespaces',
        period_label='Current Inventory Snapshot',
        data_cutoff='02 Aug 2026 15:14 UTC',
        generated_at='03 Aug 2026 12:47 UTC',
        generated_by='Platform Operations',
        classification='Internal',
    )


def _rendered_html(report_type: str) -> str:
    environment = Environment(
        loader=FileSystemLoader(PROJECT_ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    document = SimpleNamespace(
        report_name='Inventory Validation',
        presentation=_presentation(report_type),
    )
    return environment.get_template(inventory_template_for_report_type(report_type)).render(document=document)


@pytest.mark.parametrize('report_type', REPORT_TYPES)
def test_inventory_publication_uses_fixed_nine_page_contract(report_type: str) -> None:
    presentation = _presentation(report_type)

    assert presentation['page_count'] == 9
    assert presentation['layout_contract']['paper'] == 'A4 Portrait'
    assert presentation['layout_contract']['relationship_policy'] == 'committed-edges-only'
    assert len(presentation['detail_pages']) == 5


def test_inventory_methodology_keeps_included_and_excluded_side_by_side() -> None:
    rendered_html = _rendered_html('storage_inventory')
    css = (PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'inventory_publications.css').read_text(
        encoding='utf-8'
    )

    assert 'class="boundary-columns"' in rendered_html
    assert 'Included in This Report' in rendered_html
    assert 'Not Included in This Report' in rendered_html
    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)' in css
    assert 'column-gap: 14mm' in css


def test_missing_inventory_fields_remain_not_available() -> None:
    presentation = _presentation('service_inventory')
    evidence_rows = presentation['detail_pages'][3]['left']['rows']

    load_balancer_row = next(row for row in evidence_rows if row[0] == 'Load Balancer')
    assert load_balancer_row[2] == 'Not Available'


def test_inventory_renderer_registration_covers_all_templates() -> None:
    engine = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text(encoding='utf-8')
    builder = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'builder.py').read_text(
        encoding='utf-8'
    )

    assert 'build_inventory_publication_presentation' in builder
    assert 'inventory_template_for_report_type' in builder
    for report_type in REPORT_TYPES:
        template = inventory_template_for_report_type(report_type)
        assert f"'{template}': 'inventory_publications.css'" in engine


@pytest.mark.parametrize('report_type', REPORT_TYPES)
def test_inventory_publications_render_exactly_nine_a4_pages(tmp_path: Path, report_type: str) -> None:
    output_path = tmp_path / f'{report_type}.pdf'
    font_config = FontConfiguration()
    HTML(string=_rendered_html(report_type), base_url=str(PROJECT_ROOT)).write_pdf(
        target=str(output_path),
        stylesheets=[
            CSS(
                filename=str(PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'inventory_publications.css'),
                font_config=font_config,
            )
        ],
        font_config=font_config,
        presentational_hints=True,
    )

    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 9
    for page in reader.pages:
        assert 594 <= float(page.mediabox.width) <= 596
        assert 841 <= float(page.mediabox.height) <= 843
