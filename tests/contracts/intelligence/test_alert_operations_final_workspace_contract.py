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
    active_header = active.split('id="alert-operations-active-registry"', 1)[1].split('</header>', 1)[0]
    assert "loading_bar.render('alert-operations-active-loading'" in active_header
    assert active.index("loading_bar.render('alert-operations-active-loading'") < active.index('id="alert-operations-filter-form"')
    assert "metadata_label(payload.active_pagination.total_items ~ ' Alert Cases'" in active
    assert 'Clear Filters' in active
    assert 'data-resource-detail-toggle' in table
    assert 'data-alert-case-expanded-row=' not in table
    assert "resource_detail_modal.host('Alert Operations'" in page
    assert "record_pagination.render(payload.active_pagination, 'page', 'per_page', 'alert-operations-active-registry'" in table


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
    assert routing.index('Channel Readiness') < routing.index('Policy Registry')
    assert routing.count('class="{{ table_ui.action_classes() }}"') >= 2
    assert 'data-kaori-detail-variant="modal"' in editor
    assert 'Identity & Cadence' in editor
    assert 'Match Scope & Channels' in editor
    assert 'bg-kaori-soft text-kaori-primary' in editor
    assert 'Matcher tip:' in editor
    assert 'Policy Checklist' in editor
    assert 'bg-status-critical' in editor
    assert 'Delete Policy' in editor
    assert "def routing_policy_details(policy_ref: str)" in routes
    assert 'def delete_routing_policy(policy_id: int)' in routes
    assert 'def delete_routing_policy_command' in application


def test_silence_registry_has_full_kaori_filter_loading_and_pagination_contract() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_silences.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "loading_bar.render('alert-operations-silence-loading'" in template
    silence_header = template.split('id="alert-operations-silence-registry"', 1)[1].split('</header>', 1)[0]
    assert "loading_bar.render('alert-operations-silence-loading'" in silence_header
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
    assert 'data-resource-detail-toggle' in template
    assert 'alert_intelligence.case_details' in template
    assert 'Close Review' not in template


def test_notification_templates_have_posture_and_guidance_before_registry() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_templates.html')

    assert 'Notification Templates' in template
    assert 'Template Guidance' in template
    assert 'Eligible Channels' in template
    assert 'Template Registry' in template
    assert '<details class="group bg-surface-card">' in template
    assert 'Rendered Preview' in template
    assert 'Save Override' in template


def test_context_loading_is_isolated_from_tab_and_registry_loading() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')

    context_form = workspace.split('id="alert-intelligence-context-form"', 1)[1].split('</form>', 1)[0]
    assert 'hx-indicator="#alert-intelligence-context-loading"' in context_form
    assert 'hx-indicator="#alert-intelligence-loading"' not in context_form
    assert "loading_bar.render('alert-intelligence-context-loading'" in workspace
    assert "indicator_id='alert-intelligence-loading'" not in workspace
    assert "hx_indicator='#alert-intelligence-loading'" not in workspace
    assert 'table_ui.filter_layout_classes()' in context_form


def test_resolved_case_review_uses_dedicated_modal_content_and_modal_refresh_contract() -> None:
    history = read('app/templates/intelligence/partials/_alert_ops_history.html')
    modal = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    routes = read('app/intelligence/alert_intelligence/routes.py')

    assert 'data-resource-detail-toggle' in history
    assert "tab='resolved'" in history
    activity = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')
    assert 'data-kaori-detail-variant="modal"' in modal
    for required in ('Verification & Closure', 'Verification Pending', 'Resolution Evidence', 'Postmortem & Learning'):
        assert required in modal
    for required in ('Incident Timeline', 'Notification Delivery Ledger'):
        assert required in activity
    assert "if payload.get('tab') == 'resolved'" in routes
    assert "requested_tab = str(tab or request.form.get('tab') or 'active')" in routes


def test_case_modal_uses_persistent_summary_host_and_shared_activity_streams() -> None:
    active = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    resolved = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    routing = read('app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html')
    recommendation = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    modal_host = read('app/templates/components/resource_detail_modal.html')
    activity = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')

    assert 'id="resource-detail-modal-summary"' in modal_host
    assert 'data-resource-detail-summary-host' in modal_host
    assert 'data-resource-detail-summary' in recommendation
    for template in (active, resolved, routing):
        assert 'data-resource-detail-summary' in template
    for template in (active, resolved):
        assert 'hx-swap-oob="innerHTML:#resource-detail-modal-summary"' in template
        assert 'sticky top-0 z-20' not in template
    assert "_alert_ops_case_activity_streams.html" in active
    assert "_alert_ops_case_activity_streams.html" in resolved
    assert 'Incident Timeline' in activity
    assert 'Notification Delivery Ledger' in activity
    assert 'Earlier Timeline Events' in activity
    assert 'Earlier Delivery Attempts' in activity
    assert 'max-h-72' in activity


def test_routing_registry_has_canonical_filters() -> None:
    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'table_registry.filter_form' in routing
    assert 'routing_q' in routing
    assert 'routing_domain' in routing
    assert 'routing_status' in routing
    assert 'table_registry.clear_filters_action' in routing
    assert "'routing_filters': {'q': routing_search, 'domain': routing_domain, 'status': routing_status}" in service
    assert 'def _filter_routing_policies(' in service


def test_modal_case_mutations_refresh_visible_registry_via_htmx_event() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    silences = read('app/templates/intelligence/partials/_alert_ops_silences.html')
    resolved = read('app/templates/intelligence/partials/_alert_ops_history.html')

    assert "response.headers['HX-Trigger'] = 'alertCaseChanged'" in routes
    assert 'hx-trigger="alertCaseChanged from:body"' in active
    assert 'hx-trigger="alertCaseChanged from:body"' in silences
    assert 'hx-trigger="alertCaseChanged from:body"' in resolved


def test_context_filter_owns_only_context_loading_lifecycle() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    context_form = workspace.split('id="alert-intelligence-context-form"', 1)[1].split('</form>', 1)[0]

    assert 'hx-indicator="#alert-intelligence-context-loading"' in context_form
    assert 'hx-sync="this:replace"' in context_form
    assert 'hx-disinherit="hx-indicator"' in context_form
    assert 'hx-select="#alert-intelligence-page-content"' in context_form
    assert '#alert-operations-active-loading' not in context_form
    assert '#alert-operations-silence-loading' not in context_form
    assert "indicator_id='alert-intelligence-loading'" not in workspace
    assert "hx_indicator='#alert-intelligence-loading'" not in workspace


def test_alert_intelligence_modals_follow_recommendation_review_visual_language() -> None:
    active = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    resolved = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    routing = read('app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html')

    for template in (active, resolved):
        assert 'data-kaori-alert-review-layout="recommendation-inspired"' in template
        assert 'data-kaori-detail-shell' in template
        assert 'border border-brand-outline bg-kaori-soft text-kaori-primary' in template
        assert 'Committed Evidence' in template
        assert 'data-kaori-alert-status-rail' in template
        assert 'data-resource-detail-summary' in template
    assert 'Alert Case Review' in active
    assert 'Resolved Case Review' in resolved
    assert 'data-kaori-routing-modal-layout="recommendation-inspired"' in routing
    assert 'data-kaori-detail-shell' in routing
    assert 'Governed Delivery' in routing
