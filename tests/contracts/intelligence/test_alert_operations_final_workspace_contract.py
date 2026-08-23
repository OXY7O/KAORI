from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_active_queue_owns_loading_filter_actions_and_modal_review() -> None:
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    page = read('app/templates/intelligence/alert_intelligence.html')

    assert 'Active Alert Queue' in active
    assert "loading_bar.render('alert-operations-active-loading'" in active
    assert active.index("loading_bar.render('alert-operations-active-loading'") < active.index('id="alert-operations-filter-form"')
    assert "metadata_label(payload.active_pagination.total_items ~ ' Alert Cases'" in active
    assert 'Clear Filters' in active
    assert 'data-resource-detail-toggle' in table
    assert 'data-alert-case-expanded-row=' not in table
    assert "resource_detail_modal.host('Alert Operations'" in page


def test_routing_workspace_is_table_led_and_crud_uses_modal() -> None:
    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    editor = read('app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    application = read('app/intelligence/alert_intelligence/application.py')

    assert 'Routing Guidance' in routing
    assert 'Policy Registry' in routing
    assert "table_ui.table_classes('w-full table-fixed')" in routing
    assert 'overflow-x-auto' not in routing
    assert 'Policy Details' in routing
    assert 'data-resource-detail-toggle' in routing
    assert "alert_intelligence.routing_policy_details" in routing
    assert 'max-h-[30rem]' in routing
    assert 'Channel Readiness' in routing
    assert 'data-kaori-detail-variant="modal"' in editor
    assert 'Matcher tip:' in editor
    assert 'Delete Policy' in editor
    assert "def routing_policy_details(policy_ref: str)" in routes
    assert 'def delete_routing_policy(policy_id: int)' in routes
    assert 'def delete_routing_policy_command' in application


def test_silence_registry_has_full_kaori_filter_loading_and_pagination_contract() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_silences.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "loading_bar.render('alert-operations-silence-loading'" in template
    assert 'table_registry.filter_form' in template
    assert 'silence_q' in template
    assert 'silence_severity' in template
    assert 'Clear Filters' not in template  # canonical clear action macro owns the label
    assert 'table_registry.clear_filters_action' in template
    assert 'table_registry.footer' in template
    assert "'silence_filters': {'q': silence_search, 'severity': silence_severity}" in service
    assert 'def _active_silence_rows(' in service
    assert "if severity != 'all':" in service


def test_resolved_workspace_adds_posture_and_keeps_clear_next_to_archive_policy() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_history.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'Resolved Alert Posture' in template
    assert 'Evidence Retention' in template
    assert 'Archive Policy' in template
    assert 'table_registry.clear_filters_action' in template
    assert "loading_bar.render('alert-operations-history-loading'" in template
    assert "'resolved_total': len(history_cases)" in service
    assert "'closed': sum(case.workflow_state == 'closed' for case in history_cases)" in service
    assert "'false_positive': sum(case.closure_reason == 'false_positive' for case in history_cases)" in service


def test_notification_templates_have_posture_and_guidance_before_registry() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_templates.html')

    assert 'Notification Templates' in template
    assert 'Template Guidance' in template
    assert 'Eligible Channels' in template
    assert 'Template Registry' in template
    assert '<details class="group bg-surface-card">' in template
    assert 'Rendered Preview' in template
    assert 'Save Override' in template
