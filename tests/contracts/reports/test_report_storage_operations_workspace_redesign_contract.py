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


def test_storage_page_uses_balanced_hero_and_contract_first_workspace() -> None:
    template = read('app/templates/reports/storage/index.html')

    assert 'page_hero.context_actions_classes(2)' in template
    assert 'data-storage-hero-actions="balanced-two"' in template
    assert 'Verify Storage' in template
    assert 'Generated Reports' in template
    assert 'data-report-storage-posture=' in template
    assert 'data-storage-workspace-shell="true"' in template
    assert 'data-storage-overview-layout="posture-target-coverage"' in template
    assert 'data-report-storage-readiness-monitor="true"' in template
    assert 'Storage Posture' in template
    assert 'Access &amp; Readiness' in template

    assert 'data-storage-artifact-evidence="metadata-first"' in template
    assert '>References</dt>' in template
    assert 'Tracked Size' in template
    assert 'Coverage comes from Reports metadata; backend enumeration is not required.' in template
    assert 'reports/components/_summary_strip.html' not in template
    assert 'xl:grid-cols-[minmax(0,1fr)_380px]' not in template
    for raw_palette in ('emerald-', 'amber-', 'rose-', 'slate-'):
        assert raw_palette not in template


def test_storage_workspace_reuses_analytics_style_content_tabs_and_canonical_table_presentation() -> None:
    template = read('app/templates/reports/storage/index.html')

    assert 'components/content_tabs.html' in template
    assert 'content_tabs.render_links' in template
    assert "data_namespace='storage'" in template
    assert "('overview', 'Storage Overview'" in template
    assert "('integrity', 'Integrity & Verification'" in template
    assert "('retention', 'Lifecycle Governance'" in template
    assert 'components/table.html' in template
    assert 'components/table_label.html' in template
    assert 'table_ui.table_classes' in template
    assert 'table_label.status_indicator_label' in template


def test_storage_workspace_is_server_owned_and_action_results_return_to_the_right_domain() -> None:
    routes = read('app/reports/storage/routes.py')
    service = read('app/reports/storage/service.py')

    assert "workspace = normalize_storage_workspace(request.args.get('workspace'))" in routes
    assert 'get_report_storage_payload(workspace=workspace)' in routes
    assert "get_report_storage_payload(workspace='integrity')" in routes
    assert "redirect(url_for('reports.storage', workspace=workspace))" in routes
    assert 'build_storage_integrity_presentation' in routes
    assert "request.args.get('verify')" not in routes
    assert "request.args.get('cleanup_dry_run')" not in routes

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
    result = present(
        {
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
        }
    )

    assert [item['status'] for item in result['review_samples']] == ['Missing', 'Error']
    assert result['review_samples'][0]['tone'] == 'critical'
    assert result['review_samples'][1]['tone'] == 'warning'


def test_storage_integrity_and_retention_have_single_authoritative_ownership_boundary() -> None:
    template = read('app/templates/reports/storage/index.html')
    service = read('app/reports/storage/service.py')

    assert 'data-storage-integrity-actions="action-cards"' in template
    assert 'Validate the newest retained report references against their recorded backend prefix.' in service
    assert 'Read-only; nothing is deleted.' in service
    assert "url_for('reports.scan_storage_integrity')" in template

    assert 'data-storage-retention-layout="lifecycle-governance"' in template
    assert 'data-storage-retention-summary="policy-strip"' in template
    assert 'data-storage-retention-governance="split-boundary"' in template
    assert 'data-storage-lifecycle-handoff="authoritative"' in template
    assert 'Lifecycle Actions Live in Data Lifecycle' in template
    assert 'Open Data Lifecycle' in template
    assert 'Storage Candidate Preview' not in template
    assert 'build_report_cleanup_dry_run' not in service
    assert 'cleanup_dry_run' not in service


def test_storage_overview_uses_active_backend_connection_contract_not_field_cards() -> None:
    template = read('app/templates/reports/storage/index.html')

    assert 'data-storage-target-access="two-panel"' in template
    assert 'S3-compatible storage' not in template or '{{ posture.backend_label }}' in template
    assert 'data-storage-backend-connection="{{ payload.active_backend }}"' in template
    assert 'data-storage-backend-access="{{ payload.active_backend }}"' in template
    assert 'Storage Target' in template
    assert 'Access &amp; Readiness' in template
    assert 'Prefix' in template
    assert '>Credentials</dt>' in template
    assert 'Read' in template
    assert 'data-storage-configuration-boundary="true"' in template
    assert 'Storage configuration is protected and managed through {{ payload.configuration_source }}' in template
    assert 'Object Key Contract' in template

    overview = template.split("{% if payload.workspace == 'overview' %}", 1)[1].split(
        "{% elif payload.workspace == 'integrity' %}", 1
    )[0]
    assert '{% set active_items = [' not in overview
    assert 'Backend Contract' not in overview
    assert 'data-storage-posture="summary"' in overview


def test_storage_verification_is_post_only_and_object_key_copy_is_generic_asset_aware() -> None:
    routes = read('app/reports/routes.py')
    storage_routes = read('app/reports/storage/routes.py')
    storage_service = read('app/reports/storage/service.py')
    template = read('app/templates/reports/storage/index.html')

    assert "'/storage/verify'" in routes
    assert "endpoint='verify_storage'" in routes
    verify_rule = routes.split("endpoint='verify_storage'", 1)[1].split('reports_bp.add_url_rule(', 1)[0]
    assert "'POST'" in verify_rule
    assert "request.args.get('verify')" not in storage_routes
    assert "url_for('reports.verify_storage')" in template
    assert '<domain>' in storage_service
    assert '<source_kind>' in storage_service
    assert '<asset_slug>' in storage_service
    assert '<cluster_slug>' not in storage_service


def test_storage_payload_avoids_inactive_backend_walks_and_duplicate_summary_queries() -> None:
    service = read('app/reports/storage/service.py')
    health = read('app/reports/storage/health.py')

    payload = service.split('def get_report_storage_payload(', 1)[1].split('def verify_active_report_storage(', 1)[0]
    assert "build_local_storage_health() if backend_name == 'local' else None" in payload
    assert "build_s3_storage_health() if backend_name == 's3' else None" in payload
    assert 'build_storage_summary_cards' not in service
    assert 'func.sum(case(' in health
    assert 'def count_reports_with_file_path' not in health
