from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'app/reports/overview/presentation.py'
ROUTES_PATH = ROOT / 'app/reports/routes.py'


def _load_presentation_module():
    spec = importlib.util.spec_from_file_location('reports_overview_presentation', MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_previous_payload_is_normalized_to_redesigned_contract() -> None:
    module = _load_presentation_module()
    previous_payload = {
        'page_title': 'Reports Overview',
        'summary_cards': [
            {'label': 'Total Reports', 'value': '0'},
            {'label': 'Generated This Month', 'value': '0'},
            {'label': 'Ready Reports', 'value': '0'},
            {'label': 'Enabled Schedules', 'value': '0'},
        ],
        'report_type_coverage': {
            'kubernetes': {
                'label': 'Kubernetes Reports',
                'description': 'Current report contracts.',
                'items': [
                    {
                        'name': 'Analytics Overview',
                        'description': 'Overview report.',
                        'icon': 'file-text',
                        'status': 'Available',
                        'tone': 'blue',
                    }
                ],
                'available_count': 1,
                'total_count': 1,
            },
            'server': {
                'label': 'Server Reports',
                'description': 'Reserved report contracts.',
                'items': [],
                'available_count': 0,
                'total_count': 0,
            },
        },
        'pipeline_status': [
            {
                'name': 'Report Generation',
                'description': 'PDF export is available.',
                'status': 'Ready',
                'tone': 'blue',
                'icon': 'file-check-2',
            }
        ],
        'current_status': [
            {
                'label': 'Report Engine',
                'value': 'Ready',
                'description': 'Generation is available.',
                'tone': 'green',
                'icon': 'file-check-2',
            }
        ],
        'reporting_context': [
            {
                'title': 'Readable Report Contract',
                'description': 'Reports are standalone documents.',
                'icon': 'book-open-check',
                'bullets': ['Templates define sections.', 'Artifacts retain metadata.'],
            }
        ],
        'reporting_operating_model': {
            'description': 'Current operating model.',
            'cards': [
                {
                    'label': 'Artifact Storage',
                    'value': 'Local Filesystem',
                    'description': 'Local storage is selected.',
                    'icon': 'archive',
                    'tone': 'green',
                }
            ],
        },
        'data_collection_status': [
            {
                'title': 'Container Platform Data Collection',
                'status': 'Ready',
                'tone': 'blue',
                'icon': 'boxes',
                'items': ['Kubernetes inventory.', 'Prometheus metrics.'],
            }
        ],
    }

    payload = module.normalize_reports_overview_payload(previous_payload)

    assert payload['page_title'] == 'Reports Overview'
    assert payload['report_type_summary']['available'] == '1'
    assert payload['report_type_coverage']['available_count'] == 1
    assert payload['report_type_coverage']['domains'][0]['tone'] == 'normal'
    assert payload['pipeline_summary'] == {'ready': 1, 'review': 0, 'planned': 0, 'total': 1}
    assert payload['current_status_summary']['posture'] == 'Ready'
    assert payload['reporting_context'][0]['detail'] == ('Templates define sections. Artifacts retain metadata.')
    assert payload['data_collection_status'][0]['stage'] == 'ready'
    assert payload['related_information'][0]['href'] == '/reports/generate'


def test_reports_route_applies_payload_normalizer() -> None:
    routes_source = ROUTES_PATH.read_text()
    assert 'from app.reports.overview.presentation import normalize_reports_overview_payload' in routes_source
    assert 'payload = normalize_reports_overview_payload(get_reports_overview_payload())' in routes_source
