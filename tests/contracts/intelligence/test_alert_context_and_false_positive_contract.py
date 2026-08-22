from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_context_filters_do_not_submit_stale_cross_domain_asset() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'id="alert-intelligence-domain-form"' in workspace
    assert 'id="alert-intelligence-asset-form"' in workspace
    assert workspace.count('hx-trigger="change"') >= 2
    assert workspace.count('hx-include="closest form"') >= 2
    domain_form = workspace.split('id="alert-intelligence-domain-form"', 1)[1].split('</form>', 1)[0]
    asset_form = workspace.split('id="alert-intelligence-asset-form"', 1)[1].split('</form>', 1)[0]
    assert 'name="asset"' not in domain_form
    assert 'name="domain"' in domain_form
    assert 'name="domain"' in asset_form
    assert 'name="asset"' in asset_form
    assert 'option.label }} · {{ option.count' not in workspace
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
