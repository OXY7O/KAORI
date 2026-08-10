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
    assert 'data-storage-posture-layout="editorial-readiness"' in template
    assert 'Storage Decision' in template
    assert 'Automatic Storage Readiness' in template
    assert 'data-report-storage-readiness-monitor="true"' in template
    assert 'data-storage-readiness-tip="true"' in template
    assert 'Operational Tip' in template
    assert 'data-storage-decision-list="true"' in template
    assert 'data-storage-readiness-strip="true"' in template

    assert 'Tracked Artifacts' not in template
    assert 'Ready Reports' not in template
    assert 'Tracked Size' not in template
    assert 'Report Metadata' not in template
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


def test_storage_posture_keeps_only_read_write_and_state_aware_tip() -> None:
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
    assert ready['tip_title'] == 'Use Strong Verification for Recovery Events'
    assert 'lightweight' in ready['tip_text']

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
    assert degraded['tip_title'] == 'Complete Strong Verification Before Resuming Writes'

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
    assert disconnected['read_label'] == 'Paused'
    assert disconnected['write_label'] == 'Paused'
    assert disconnected['tip_title'] == 'Restore Connectivity First'


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


def test_storage_integrity_and_retention_use_editorial_boundaries_not_card_grids() -> None:
    template = read('app/templates/reports/storage/index.html')
    service = read('app/reports/storage/service.py')

    assert 'data-storage-integrity-actions="split-workspace"' in template
    assert 'Validate stored report references against the active backend. Read-only; nothing is deleted.' in service
    assert 'Use Check Artifact Integrity to validate database file_path references' not in service

    assert 'data-storage-retention-layout="editorial-policy"' in template
    assert 'data-storage-retention-summary="policy-strip"' in template
    assert 'data-storage-retention-governance="split-boundary"' in template
    assert 'data-storage-cleanup-action="inline-boundary"' in template
    assert 'Retention identifies review candidates; deletion remains explicitly governed.' in template
    assert 'Preview records that match retention rules without deleting artifacts or database rows.' in service

    # Regression guards against the previous card-heavy retention layout only.
    retention = template.split('data-storage-retention-layout="editorial-policy"', 1)[1]
    assert '<div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">' not in retention
    assert '<div class="mt-4 grid gap-4 lg:grid-cols-2">' not in retention
    assert 'rounded-xl border border-outline-subtle bg-surface-subtle p-4' not in retention
