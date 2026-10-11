from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_context_filters_submit_one_canonical_form_state() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'id="alert-intelligence-context-form"' in workspace
    context_form = workspace.split('id="alert-intelligence-context-form"', 1)[1].split('</form>', 1)[0]
    assert 'hx-get="{{ url_for(\'alert_intelligence.index\') }}"' in context_form
    assert 'hx-trigger="change"' in context_form
    assert 'hx-target="#alert-intelligence-page-content"' in context_form
    assert 'hx-push-url="true"' in context_form
    assert 'hx-sync="this:replace"' in context_form
    assert 'id="alert-intelligence-domain-select"' in context_form
    assert 'id="alert-intelligence-asset-select"' in context_form
    assert 'name="domain"' in context_form
    assert 'name="asset"' in context_form
    assert 'hx-disabled-elt=' not in context_form
    assert 'hx-include=' not in context_form
    assert 'table_ui.filter_layout_classes()' in workspace
    assert 'option.label }} · {{ option.count' not in workspace

    # Cross-domain selection retains the legacy fleet behavior for Kubernetes/Storage.
    # Registry direct deep links are special: invalid/disabled scope must fail closed.
    assert 'domain = _selected_domain(args, clusters=clusters, systems=systems)' in service
    assert 'assets = _asset_options(domain, clusters=clusters, systems=systems)' in service
    assert 'selected_asset_key = _selected_asset_key(args, assets, domain=domain)' in service
    assert "return _INVALID_REGISTRY_SCOPE if domain == 'registry' else 'all'" in service
    assert "{'value': 'kubernetes', 'label': 'Kubernetes'}" in service
    assert "{'value': 'registry', 'label': 'Artifact Registry'}" in service
    assert 'scope_invalid = selected_asset_key == _INVALID_REGISTRY_SCOPE' in service
    assert 'scoped_cases = [] if scope_invalid else _case_rows(' in service
    assert 'get_case(requested)' not in service
    assert 'Select an Active Registry Provider' in workspace
    assert "payload.domain == 'registry' and payload.tab == 'routing'" in workspace


def test_registry_alert_intelligence_handoff_and_notification_policy_are_explicit() -> None:
    summary = read('app/templates/artifact_registry/partials/_overview_alerts_summary.html')
    service = read('app/intelligence/alert_intelligence/service.py')
    routing = read('app/intelligence/alert_intelligence/routing.py')
    notifications = read('app/intelligence/alert_intelligence/notifications.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    route_support = read('app/intelligence/alert_intelligence/route_utils.py')

    assert "domain='registry', asset=overview.selected_provider_id, tab='active'" in summary
    assert "_VALID_DOMAINS = {'kubernetes', 'object_storage', 'registry'}" in service
    assert "IntegrationInstance.integration_type == 'registry'" in service
    assert "IntegrationInstance.enabled.is_(True)" in service
    assert "IntegrationInstance.lifecycle_status == 'active'" in service
    assert 'scope_invalid = selected_asset_key == _INVALID_REGISTRY_SCOPE' in service
    assert 'if scope_invalid:' in workspace
    assert 'Select an Active Registry Provider' in workspace
    assert "payload.domain == 'registry' and payload.tab == 'routing'" in workspace
    assert 'Registry Notification Routing Is Not Enabled' in workspace
    assert 'get_case(requested)' not in service
    assert "return next((case for case in rows if case.public_id == requested), None)" in service
    assert 'payload.get(\'selected_case\') is None' in route_support
    assert 'return (\'Alert case not found.\', 404)' in route_support
    assert "if 'registry' in config.domains:" in routing
    assert "if case.domain == 'registry':" in routing
    assert "if case.domain == 'registry':" in notifications
    assert "'domain': case.domain, 'asset': case.asset_key, 'case': case.public_id" in notifications


def test_false_positive_is_governed_closure_without_source_resolution() -> None:
    model = read('app/models/alert_ops.py')
    state = read('app/intelligence/alert_intelligence/case_state.py')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "'false_positive'" in model
    assert 'def close_false_positive_alert(' in state
    assert "case.closure_reason = 'false_positive'" in state
    assert 'state.promotion_suppressed_until_clear = True' in state
    assert "state.promotion_suppression_reason = 'false_positive'" in state
    assert (
        "case.source_state = 'resolved'"
        not in state.split('def close_false_positive_alert(', 1)[1].split('def retire_source_deleted_case(', 1)[0]
    )
    assert "/false-positive'" in routes
    assert 'Close as False Positive' in workspace
    assert "'false_positive': 'False Positive'" in service


def test_false_positive_migration_extends_closure_reason_constraint() -> None:
    migration = read('migrations/versions/20260823_alert_false_positive.py')

    assert "revision = '20260823_alert_false_positive'" in migration
    assert "down_revision = '20260822_alert_source_unknown'" in migration
    assert "'false_positive'" in migration
