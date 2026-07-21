from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_loading_bar_matches_activity_audit_contract() -> None:
    activity = read("app/templates/notifications/partials/_activity_table_card.html")
    shared = read("app/templates/components/loading_bar.html")
    for fragment in (
        "mt-4 h-1 overflow-hidden rounded-full bg-kaori-soft",
        "h-full w-1/3 animate-pulse rounded-full bg-kaori-primary",
    ):
        assert fragment in activity
        assert fragment in shared


def test_provider_operational_blocks_render_loading_inside_header() -> None:
    shared_header = read("app/templates/components/connection_validation_header.html")
    assert "loading_bar.render" in shared_header
    expectations = {
        "app/templates/prometheus/partials/_detail_validation_content.html": "prometheus-validation-loading",
        "app/templates/alertmanager/partials/_detail_validation_content.html": "alertmanager-validation-loading",
        "app/templates/integrations/kubernetes/partials/_capability_workspace.html": "kubernetes-capability-loading",
        "app/templates/integrations/kubernetes/partials/_runtime_workspace.html": "kubernetes-runtime-validation-loading",
    }
    for relative, loading_id in expectations.items():
        source = read(relative)
        assert f"loading_id='{loading_id}'" in source
        assert f'hx-indicator="#{loading_id}"' in source


def test_runtime_history_and_jobs_use_shared_header_loading_bar() -> None:
    expectations = {
        "app/templates/integrations/partials/_runtime_history.html": "loading_bar.render(runtime_history_loading_id",
        "app/templates/integrations/jobs/partials/_workspace.html": "loading_bar.render('job-workspace-loading'",
        "app/templates/integrations/jobs/partials/_active_jobs.html": "loading_bar.render('active-job-loading'",
        "app/templates/integrations/jobs/partials/_registry.html": "loading_bar.render('job-execution-loading'",
        "app/templates/prometheus/partials/_runtime_panel.html": "loading_bar.render(",
        "app/templates/alertmanager/partials/_runtime_panel.html": "loading_bar.render(",
    }
    for relative, fragment in expectations.items():
        source = read(relative)
        assert 'components/loading_bar.html' in source
        assert fragment in source
