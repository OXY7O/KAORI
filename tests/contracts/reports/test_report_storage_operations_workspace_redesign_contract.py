from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def load_service_symbols(*names: str) -> dict[str, object]:
    source = read('app/reports/storage/service.py')
    tree = ast.parse(source)
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any(target in names for target in targets):
                selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            selected.append(node)
    namespace: dict[str, object] = {'Any': Any}
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<storage-service-contract>', 'exec'), namespace)
    return namespace


def test_storage_page_uses_balanced_hero_and_one_state_aware_posture() -> None:
    template = read('app/templates/reports/storage/index.html')

    assert 'page_hero.context_actions_classes(2)' in template
    assert 'data-storage-hero-actions="balanced-two"' in template
    assert 'Verify Storage' in template
    assert 'Generated Reports' in template
    assert 'data-report-storage-posture=' in template
    assert 'Storage Operations Posture' in template
    assert 'Automatic Storage Readiness' in template
    assert 'data-report-storage-readiness-monitor="true"' in template

    assert 'reports/components/_summary_strip.html' not in template
    assert 'xl:grid-cols-[minmax(0,1fr)_380px]' not in template
    for raw_palette in ('emerald-', 'amber-', 'rose-', 'slate-'):
        assert raw_palette not in template


def test_storage_workspace_reuses_framed_tabs_and_canonical_table_presentation() -> None:
    template = read('app/templates/reports/storage/index.html')

    assert 'components/framed_workspace_tabs.html' in template
    assert 'framed_tabs.render_navigation' in template
    assert "('overview', 'Storage Overview'" in template
    assert "('integrity', 'Integrity & Verification'" in template
    assert "('retention', 'Retention & Cleanup'" in template
    assert 'components/table.html' in template
    assert 'components/table_label.html' in template
    assert 'table_ui.table_classes' in template
    assert 'table_label.status_indicator_label' in template


def test_storage_workspace_is_server_owned_and_action_results_return_to_the_right_domain() -> None:
    routes = read('app/reports/storage/routes.py')
    service = read('app/reports/storage/service.py')

    assert "get_report_storage_payload(workspace='integrity')" in routes
    assert "get_report_storage_payload(workspace='retention')" in routes
    assert "workspace = normalize_storage_workspace(request.args.get('workspace'))" in routes
    assert "get_report_storage_payload(workspace=workspace)" in routes
    assert "redirect(url_for('reports.storage', workspace=workspace))" in routes
    assert 'build_storage_integrity_presentation' in routes

    assert 'STORAGE_WORKSPACES' in service
    assert 'normalize_storage_workspace' in service
    assert "'workspace': normalize_storage_workspace(workspace)" in service


def test_storage_workspace_normalization_is_deterministic() -> None:
    symbols = load_service_symbols('STORAGE_WORKSPACES', 'normalize_storage_workspace')
    normalize = symbols['normalize_storage_workspace']

    assert normalize(None) == 'overview'
    assert normalize('integrity') == 'integrity'
    assert normalize('RETENTION') == 'retention'
    assert normalize('unknown-workspace') == 'overview'


def test_storage_posture_separates_metadata_read_and_write_availability() -> None:
    symbols = load_service_symbols('build_storage_operations_posture')
    build = symbols['build_storage_operations_posture']
    monitor = {
        'enabled': True,
        'checked_label': 'Checked 1 min ago',
        'source_label': 'Periodic probe',
    }
    artifacts = {
        'ready_reports': 12,
        'reports_with_files': 10,
        'total_size': '1.2 GiB',
    }

    ready = build(
        backend_name='s3',
        backend_status={
            'label': 'S3-compatible storage',
            'read_available': True,
            'write_available': True,
            'reachable': True,
            'write_verification_required': False,
        },
        artifact_summary=artifacts,
        readiness_monitor=monitor,
    )
    assert ready['status_label'] == 'Storage Ready'
    assert ready['read_label'] == 'Available'
    assert ready['write_label'] == 'Ready'
    assert ready['metadata_label'] == 'Available'

    degraded = build(
        backend_name='s3',
        backend_status={
            'label': 'S3-compatible storage',
            'read_available': True,
            'write_available': False,
            'reachable': True,
            'write_verification_required': True,
        },
        artifact_summary=artifacts,
        readiness_monitor=monitor,
    )
    assert degraded['status_label'] == 'Verification Required'
    assert degraded['read_label'] == 'Available'
    assert degraded['write_label'] == 'Paused'
    assert degraded['verification_label'] == 'Required'

    disconnected = build(
        backend_name='s3',
        backend_status={
            'label': 'S3-compatible storage',
            'read_available': False,
            'write_available': False,
            'reachable': False,
            'write_verification_required': False,
        },
        artifact_summary=artifacts,
        readiness_monitor=monitor,
    )
    assert disconnected['status_label'] == 'Disconnected'
    assert disconnected['metadata_label'] == 'Available'
    assert disconnected['read_label'] == 'Paused'
    assert disconnected['write_label'] == 'Paused'


def test_integrity_samples_are_presented_as_registry_rows_not_freeform_cards() -> None:
    symbols = load_service_symbols('build_storage_integrity_presentation')
    present = symbols['build_storage_integrity_presentation']
    result = present({
        'missing_samples': [
            {
                'report_id': 41,
                'name': 'Capacity Analysis Report',
                'backend': 's3',
                'file_path': 's3:reports/41.pdf',
            }
        ],
        'error_samples': [
            {
                'report_id': 42,
                'name': 'Storage Analysis Report',
                'backend': 's3',
                'file_path': 's3:reports/42.pdf',
                'error': 'Endpoint unavailable',
            }
        ],
    })

    assert [item['status'] for item in result['review_samples']] == ['Missing', 'Error']
    assert result['review_samples'][0]['tone'] == 'critical'
    assert result['review_samples'][1]['tone'] == 'warning'
