from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_active_alert_review_expands_inline_without_full_page_reload() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')

    assert "target == 'alert-operations-active-records'" in routes
    assert "_alert_ops_active_table.html" in routes
    assert 'def _active_records_htmx_request()' in routes
    assert 'def _active_records_response(' in routes
    assert "{% include 'intelligence/partials/_alert_ops_case_workspace.html' %}" not in active
    assert 'data-alert-case-expanded-row=' in table
    assert "{% include 'intelligence/partials/_alert_ops_case_workspace.html' %}" in table
    assert 'hx-target="#alert-operations-active-records"' in table
    assert 'hx-swap="outerHTML show:none focus-scroll:false"' in table
    assert 'hx-push-url="true"' in table
    assert 'data-alert-case-review=' in workspace
    assert 'hx-target="#alert-operations-active-records"' in workspace
    assert 'Actions update this expanded row through HTMX' in workspace


def test_active_alert_list_keeps_long_evidence_out_of_scan_view() -> None:
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')

    assert '· {{ case.summary }}' not in table
    assert '{{ case.asset_name }}' in table
    assert "{% if case.namespace != '-' %}· {{ case.namespace }}{% endif %}" in table
    assert '· {{ case.source_type_label }}' in table
    assert '{{ case.summary }}' not in table


def test_alert_review_uses_full_width_stacked_incident_workspace() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "xl:grid-cols-[minmax(0,1.45fr)_minmax(25rem,0.55fr)]" not in workspace
    assert '<aside' not in workspace
    for label in (
        'Operator Actions',
        'Operational Evidence',
        'Incident Brief',
        'Incident Timeline',
        'Notification Delivery Ledger',
    ):
        assert label in workspace
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
    assert "if _active_records_htmx_request():" in routes
    assert "return _active_records_response(case_id=case.public_id)" in routes
    assert "operation_feedback_oob.html" in read('app/templates/intelligence/partials/_alert_ops_active_table.html')
