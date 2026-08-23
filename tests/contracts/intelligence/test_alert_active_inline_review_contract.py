from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_active_alert_review_opens_focused_modal_without_expanding_table_rows() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    page = read('app/templates/intelligence/alert_intelligence.html')
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')

    assert "def case_details(public_id: str)" in routes
    assert "resource_detail_modal.host('Alert Operations'" in page
    assert 'data-resource-detail-toggle' in table
    assert 'data-detail-type="Alert Case"' in table
    assert 'data-alert-case-expanded-row=' not in table
    assert "{% include 'intelligence/partials/_alert_ops_case_workspace.html' %}" not in table
    assert 'data-kaori-detail-variant="modal"' in workspace
    assert 'data-resource-detail-header' in workspace
    assert 'id="alert-case-modal-content-{{ case.public_id }}"' in workspace
    assert '</section>\n</div>\n{% endif %}\n<div id="alert-case-modal-content' not in workspace
    assert 'hx-target="#alert-case-modal-content-{{ case.public_id }}"' in workspace
    assert 'Manage ownership, delivery, and remediation without leaving this alert.' in workspace


def test_active_alert_list_keeps_long_evidence_out_of_scan_view() -> None:
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')

    assert '· {{ case.summary }}' not in table
    assert '{{ case.asset_name }}' in table
    assert "{% if case.namespace != '-' %}· {{ case.namespace }}{% endif %}" in table
    assert '· {{ case.source_type_label }}' in table
    assert '{{ case.summary }}' not in table


def test_alert_review_uses_full_width_stacked_incident_workspace() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    activity = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "xl:grid-cols-[minmax(0,1.45fr)_minmax(25rem,0.55fr)]" not in workspace
    assert '<aside' not in workspace
    for label in ('Operator Actions', 'Operational Evidence', 'Incident Brief'):
        assert label in workspace
    for label in ('Incident Timeline', 'Notification Delivery Ledger'):
        assert label in activity
    assert "'evidence_facts': _evidence_facts(evidence)" in service
    assert "'icon': _timeline_event_icon(event.event_type)" in service
    assert "'tone': _timeline_event_tone(event.event_type)" in service
    assert "'owner_user_id': case.owner_user_id" in service


def test_operator_actions_preserve_no_javascript_fallback_and_htmx_updates() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    routes = read('app/intelligence/alert_intelligence/routes.py')

    for action in (
        'alert_intelligence.acknowledge',
        'alert_intelligence.assign',
        'alert_intelligence.mitigating',
        'alert_intelligence.suppress_routing',
        'alert_intelligence.resume_routing',
        'alert_intelligence.silence',
        'alert_intelligence.unsilence',
        'alert_intelligence.withdraw',
        'alert_intelligence.retire_source',
        'alert_intelligence.close',
    ):
        assert f"action=\"{{{{ url_for('{action}'" in workspace
        assert f"htmx_form_attrs(url_for('{action}'" in workspace
    assert 'def _modal_case_htmx_request()' in routes
    assert 'def _modal_case_response(' in routes
    assert "return _modal_case_response(case_id=case.public_id, tab=tab)" in routes
    assert "operation_feedback_oob.html" in read('app/templates/intelligence/partials/_alert_ops_active_table.html')


def test_review_polish_uses_single_modal_close_and_enriches_operator_controls() -> None:
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')

    assert "metadata_label('Reviewing', 'panel-top')" not in table
    assert 'Close Review' not in workspace
    assert 'data-resource-detail-toggle' in table
    assert 'Take ownership and pause repeats during the ACK window.' in workspace
    assert 'Assign the operator responsible for follow-up.' in workspace
    assert "status_label(case.delivery_label, case.delivery_tone, size='compact')" in workspace
    assert '>Routing</dt>' in workspace
    assert '>Channel</dt>' in workspace
    assert 'Routing active; delivery follows policy cadence.' in workspace


def test_review_evidence_and_timeline_use_horizontal_scan_layout() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    for label in ('Source', 'Source Type', 'Rule Key', 'Recommendation Count'):
        assert f"'{label}'" in workspace
    assert 'md:grid-cols-4' in workspace
    assert "case.evidence.get('recommendation_count', 1)" in workspace
    activity = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')
    assert 'sm:grid-cols-[2rem_minmax(0,1fr)_9rem]' in activity
    assert 'Notification Delivery Ledger' in activity
    for key in ("'source'", "'source_type'", "'rule_key'", "'recommendation_count'"):
        assert key in service


def test_routes_import_routing_state_mutations_from_case_state_owner() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')

    assert 'from app.intelligence.alert_intelligence.case_state import (' in routes
    for name in (
        'resume_case_routing',
        'retire_source_deleted_case',
        'suppress_case_routing',
        'withdraw_manual_alert',
    ):
        assert name in routes
    lifecycle_block = (
        routes.split('from app.intelligence.alert_intelligence.lifecycle import (', 1)[1]
        .split(')', 1)[0]
    )
    assert 'resume_case_routing' not in lifecycle_block
    assert 'retire_source_deleted_case' not in lifecycle_block
    assert 'suppress_case_routing' not in lifecycle_block
    assert 'withdraw_manual_alert' not in lifecycle_block


def test_review_keeps_detail_summary_single_source_and_bounds_long_evidence_lists() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    activity = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'Operational AlertCase for ownership, delivery control, evidence, and verified resolution.' in workspace
    assert workspace.count('{{ case.summary }}') == 1
    assert '>Target</dt>' in workspace
    assert "('boxes', 'Asset', case.asset_name)" in workspace
    assert "('layers-3', 'Namespace', case.namespace)" in workspace
    assert "timeline_recent = timeline[-5:]" in service
    assert "timeline_older = timeline[:-5]" in service
    assert "deliveries_recent = deliveries[:5]" in service
    assert "deliveries_older = deliveries[5:]" in service
    assert 'Earlier Timeline Events' in activity
    assert 'Earlier Delivery Attempts' in activity
    assert 'max-h-72' in activity
