from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_generated_registry_uses_generic_infrastructure_scope_filter() -> None:
    service = read('app/reports/generated/service.py')
    page = read('app/templates/reports/generated/index.html')

    assert 'ObjectStorageSystem' in service
    assert "'scopes': _get_scope_options()" in service
    assert "'scope': scope" in service
    assert "scope = f'{KUBERNETES_CLUSTER_ASSET_TYPE}:{legacy_cluster_id}'" in service
    assert "'label': 'All Infrastructure Assets'" in service
    assert "'label': f'Kubernetes · {cluster.name}'" in service
    assert "'label': f'Object Storage · {system.name}'" in service
    assert 'Report.scope_asset_type == asset_type' in service
    assert 'Report.scope_asset_id == asset_id' in service
    assert 'Report.scope_asset_label_snapshot.ilike(' in service

    assert 'Infrastructure Asset' in page
    assert 'name="scope"' in page
    assert 'payload.filter_options.scopes' in page
    assert 'payload.selected_filters.scope' in page
    assert 'Kubernetes Cluster</span>' not in page
    assert 'Search report or scope...' in page


def test_generated_registry_actions_are_permission_aware() -> None:
    page = read('app/templates/reports/generated/index.html')
    detail = read('app/templates/reports/generated/detail.html')

    assert "current_user.has_permission('reports.generate')" in page
    assert "current_user.has_permission('reports.manage_storage')" in page
    assert '{% if can_manage_storage %}' in page
    assert '{% if can_generate_reports %}' in page
    assert "hero_action_label = 'Generate Report' if can_generate_reports else 'Reports Overview'" in page
    assert 'colspan="{{ 7 if can_manage_storage else 6 }}"' in page

    assert "current_user.has_permission('reports.generate')" in detail
    assert "current_user.has_permission('reports.manage_storage')" in detail
    assert 'can_generate_reports and payload.report.can_generate_artifact' in detail
    assert 'can_manage_storage and payload.report.can_archive_report' in detail
    assert 'can_manage_storage and payload.report.can_restore_report' in detail
    assert 'hero_storage_action = payload.artifact_access_notice and can_manage_storage' in detail


def test_generated_registry_polling_is_filter_scoped_and_preserves_operator_selection() -> None:
    service = read('app/reports/generated/service.py')
    page = read('app/templates/reports/generated/index.html')

    assert 'def _has_pending_reports_for_filters(selected_filters: dict[str, str]) -> bool:' in service
    assert 'selected_status and selected_status not in PENDING_STATUSES' in service
    assert "pending_filters['status']" in service
    assert 'Report.status.in_(PENDING_STATUSES)' in service
    assert 'has_pending_reports = _has_pending_reports_for_filters(selected_filters)' in service

    assert 'hx-trigger="every {{ payload.poll_interval_seconds }}s"' in page
    assert 'event.detail.elt === this' in page
    assert "this.querySelector('.generated-report-checkbox:checked')" in page
    assert 'event.preventDefault()' in page


def test_generated_archive_transition_uses_one_canonical_status_contract() -> None:
    service = read('app/reports/generated/service.py')

    assert 'ARCHIVABLE_STATUSES = (' in service
    assert "'requested',\n    'failed',\n    'ready'," in service
    assert 'Report.status.in_(ARCHIVABLE_STATUSES)' in service
    assert "'can_archive_report': report.status in ARCHIVABLE_STATUSES" in service
    assert 'if report.status not in ARCHIVABLE_STATUSES:' in service
    assert 'Queued reports cannot be archived' not in service


def test_generated_detail_polls_only_while_report_or_latest_attempt_is_active() -> None:
    service = read('app/reports/generated/service.py')
    detail = read('app/templates/reports/generated/detail.html')

    assert (
        "should_poll = report.status in PENDING_STATUSES or bool(job_execution and job_execution['is_active'])"
        in service
    )
    assert "'poll_interval_seconds': 8 if should_poll else None" in service
    assert "hx-get=\"{{ url_for('reports.generated_report_detail'" in detail
    assert 'hx-trigger="every {{ payload.poll_interval_seconds }}s"' in detail
    assert 'hx-select="[data-generated-report-detail]"' in detail
    assert "this.querySelector('dialog[open]')" in detail


def test_generated_detail_does_not_build_unrendered_legacy_context() -> None:
    service = read('app/reports/generated/service.py')
    payload_body = service.split('def get_report_detail_payload(', 1)[1].split('\n\ndef get_summary_cards', 1)[0]

    for unused_key in ('status_context', 'export_readiness', 'storage_context', 'recommended_actions'):
        assert f"'{unused_key}':" not in payload_body

    assert "'artifact_access_notice': get_report_artifact_access_notice(" in payload_body


def test_archived_missing_artifact_is_not_offered_as_restorable_evidence() -> None:
    service = read('app/reports/generated/service.py')
    detail = read('app/templates/reports/generated/detail.html')

    assert (
        "'can_restore_report': report.status == 'archived' and bool(artifact_access['reachable']) and file_exists"
        in service
    )
    assert 'Archived report storage is temporarily unavailable. Restore connectivity and retry.' in service
    assert 'Recover the retained storage reference before restoring this historical record.' in service
    assert 'Recover the retained artifact before restoring this historical record.' in service
    assert 'data-generated-detail-archived-artifact-missing="true"' in detail
    assert "payload.report.raw_status == 'archived' and not payload.report.can_restore_report" in detail
    assert 'Archived Artifact Missing' in detail
    assert 'artifact or storage reference is not currently restorable' in detail
    assert 'create a new report if fresh evidence is required' in detail


def test_generated_storage_notice_follows_full_backend_readiness_not_connectivity_only() -> None:
    service = read('app/reports/generated/service.py')

    assert "if not bool(backend_status.get('available', False)):" in service
    assert (
        "if not bool(backend_status.get('reachable', False)):"
        not in service.split('def get_generated_reports_payload(', 1)[1].split('\n\ndef get_report_detail_payload', 1)[
            0
        ]
    )
    assert 'storage-dependent operations follow' in service


def test_generated_detail_preserves_filtered_registry_return_context() -> None:
    routes = read('app/reports/generated/routes.py')
    page = read('app/templates/reports/generated/index.html')
    detail = read('app/templates/reports/generated/detail.html')

    assert 'def _generated_registry_return_url(value: object) -> str:' in routes
    assert 'candidate = safe_next_url(value)' in routes
    assert "candidate == '/reports/generated'" in routes
    assert "candidate.startswith('/reports/generated?')" in routes
    assert "payload['registry_return_url'] = registry_return_url" in routes

    assert "registry_return_url = request.full_path.rstrip('?')" in page
    assert "report_id=report.id, next=registry_return_url" in page
    assert 'else payload.registry_return_url' in detail
    assert 'next=payload.registry_return_url' in detail
    assert '<a href="{{ payload.registry_return_url }}"' in detail


def test_generated_registry_bulk_archive_selection_has_operator_guardrails() -> None:
    page = read('app/templates/reports/generated/index.html')

    assert 'selectedCount: 0' in page
    assert 'selectableCount: 0' in page
    assert 'syncSelection(root)' in page
    assert ':disabled="selectedCount === 0"' in page
    assert 'x-text="selectedCount"' in page
    assert ':disabled="selectableCount === 0"' in page
    assert '@change="syncSelection($root)"' in page
    assert '$el.indeterminate = selectedCount > 0 && selectedCount < selectableCount' in page


def test_generated_service_removed_unrendered_legacy_presentation_debt() -> None:
    service = read('app/reports/generated/service.py')
    baseline = read('docs/architecture/code-health-debt-baseline.json')

    for function_name in (
        'get_hero_posture',
        'get_lifecycle_status',
        'get_storage_context',
        'get_recommended_actions',
        'get_report_detail_status_context',
        'get_report_detail_export_readiness',
        'get_report_detail_recommended_actions',
        '_count_missing_artifacts',
        '_report_file_exists',
    ):
        assert f'def {function_name}(' not in service

    assert 'app/reports/generated/service.py::get_report_detail_recommended_actions' not in baseline
    assert '"app/reports/generated/service.py": 1688' in baseline
