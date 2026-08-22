from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_recommendation_alert_escalation_is_durable_and_worker_owned() -> None:
    model = read('app/models/alert_ops.py')
    migration = read('migrations/versions/20260822_recommendation_alert_escalation.py')
    worker = read('app/platform_operations/notifications/alert_delivery/tasks.py')
    recommendation_source = read('app/intelligence/alert_intelligence/recommendation_source.py')

    assert 'class RecommendationAlertPolicy' in model
    assert 'class RecommendationAlertState' in model
    assert 'source_type: Mapped[str]' in model
    assert 'source_ref: Mapped[str | None]' in model
    assert 'rule_key: Mapped[str | None]' in model
    assert 'source_types_json: Mapped[list[str]]' in model
    assert "revision = '20260822_reco_alert_escalation'" in migration
    assert "down_revision = '20260822_alert_operations'" in migration
    assert "'recommendation_alert_policies'" in migration
    assert "'recommendation_alert_states'" in migration
    assert "'source_types_json'" in migration
    source_default = next(line for line in migration.splitlines() if 'server_default=sa.text' in line)
    assert 'provider_alert' in source_default
    assert 'recommendation' not in source_default
    assert 'reconcile_recommendation_alert_cases()' in worker
    assert 'get_active_recommendation_findings()' in recommendation_source
    assert "policy['mode'] != 'automatic'" in recommendation_source
    assert '_automatic_threshold_reached' in recommendation_source


def test_recommendations_expose_manual_promotion_and_alert_case_traceability() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    records = read('app/templates/intelligence/partials/_recommendation_records.html')
    detail = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    case_workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')

    assert "@alert_intelligence_bp.post('/recommendations/<path:recommendation_key>/promote')" in routes
    assert "permission_required('intelligence.decisions.create')" in routes
    assert 'Alert Handling' in records
    assert 'Promote to Alert' in detail
    assert 'Promote Now' in detail
    assert 'Open Alert Case' in detail
    for current_macro in (
        'table_ui.head_classes()',
        'table_ui.header_cell_classes()',
        'table_ui.body_classes()',
        'table_ui.cell_classes()',
    ):
        assert current_macro in detail
    for retired_macro in (
        'table_ui.thead_classes()',
        'table_ui.th_classes()',
        'table_ui.tbody_classes()',
        'table_ui.td_classes()',
    ):
        assert retired_macro not in detail
    assert 'Open Source Recommendation' in case_workspace
    assert "case.source_type == 'recommendation'" in case_workspace


def test_rule_catalog_owns_recommendation_alert_eligibility_policy() -> None:
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')
    alerting = read('app/intelligence/recommendation_alerting.py')
    commands = read('app/intelligence/recommendation_alert_commands.py')

    for required in (
        'Alert Escalation',
        'Recommendation Only',
        'Manual',
        'Automatic',
        'Stability Window',
        'Minimum Observations',
        'Rule + Asset + Scope',
    ):
        assert required in detail
    assert "severity in {'warning', 'critical'}" in alerting
    assert "logic_type != 'alert_enrichment'" in alerting
    assert "audit.action = 'recommendation_alert_policy_updated'" in commands


def test_alert_routing_is_locked_to_kaori_recommendation_cases_for_current_scope() -> None:
    routing = read('app/intelligence/alert_intelligence/routing.py')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    template = read('app/templates/intelligence/partials/_alert_ops_routing.html')

    assert "KAORI_ALERT_SOURCE_TYPE = 'recommendation'" in routing
    assert 'source_types: list[str]' in routing  # schema stays future-ready
    assert 'normalized_source_types = [KAORI_ALERT_SOURCE_TYPE]' in routing
    assert 'if case.source_type != KAORI_ALERT_SOURCE_TYPE' in routing
    assert "source_types=request.form.getlist('source_types')" in routes
    assert 'KAORI Recommendations' in template
    assert 'name="source_types" value="recommendation"' in template
    assert 'Provider Alerts' not in template


def test_provider_and_recommendation_reconciliation_do_not_own_each_others_cases() -> None:
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    recommendation_source = read('app/intelligence/alert_intelligence/recommendation_source.py')

    assert "AlertCase.source_type == 'provider_alert'" in lifecycle
    assert "case.source_type = 'recommendation'" in recommendation_source
    assert 'case.source_ref = finding_key' in recommendation_source
    assert "'recommendation_source_reopened'" in recommendation_source
    assert "case.workflow_state = 'open'" in recommendation_source


def test_alert_case_workspace_exposes_only_kaori_recommendation_cases() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    history = read('app/templates/intelligence/partials/_alert_ops_history.html')

    assert "_VALID_SOURCE_TYPES = {'all', 'recommendation'}" in service
    assert "AlertCase.source_type == 'recommendation'" in service
    assert "row.source_state in {'firing', 'unknown'}" in service
    assert "row.source_state == 'resolved' or row.workflow_state == 'closed'" in service
    for template in (active, history):
        assert 'Provider Alerts' not in template


def test_recommendations_can_filter_large_finding_sets_by_alert_handling() -> None:
    service = read('app/intelligence/service.py')
    alerting = read('app/intelligence/recommendation_alerting.py')
    workspace = read('app/templates/intelligence/partials/_recommendations_workspace.html')
    filters = read('app/templates/intelligence/partials/_filters.html')

    assert "'alert_handling': clean(args.get('alert_handling'))" in service
    assert 'matches_alert_handling(' in service
    assert 'def matches_alert_handling(' in alerting
    assert "'manual_eligible'" in alerting
    assert "'automatic_eligible'" in alerting
    assert "'recommendation_only'" in alerting
    assert 'filter_include_alert_handling = true' in workspace
    assert 'name="alert_handling"' in filters
    assert 'All Alert Handling' in service
