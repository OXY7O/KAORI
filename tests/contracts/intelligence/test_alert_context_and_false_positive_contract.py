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

    # A stale asset from the previous domain is safe because the server validates it
    # against the newly selected domain and canonicalizes invalid values to fleet scope.
    assert 'domain = _selected_domain(args, clusters=clusters, systems=systems)' in service
    assert 'assets = _asset_options(domain, clusters=clusters, systems=systems)' in service
    assert 'selected_asset_key = _selected_asset_key(args, assets)' in service
    assert "return requested if requested in valid else 'all'" in service
    assert "{'value': 'kubernetes', 'label': 'Kubernetes'}" in service


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
