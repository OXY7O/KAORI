from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_binding_contract_uses_standard_kaori_typography() -> None:
    source = read("app/templates/components/integration_coverage_content.html")
    assert 'font-mono text-xs text-content-secondary' not in source
    assert 'text-xs font-medium text-content-secondary' in source


def test_job_registry_refreshes_current_view_with_htmx() -> None:
    source = read("app/templates/integrations/jobs/partials/_registry.html")
    assert 'Refresh' in source
    assert 'data-lucide="refresh-cw"' in source
    assert 'hx-target="#job-execution-registry"' in source
    assert 'hx-swap="outerHTML"' in source
    assert 'hx-indicator="#job-execution-loading"' in source
    assert 'page=job_pagination.page' in source
    assert 'per_page=job_pagination.per_page' in source


def test_prometheus_and_alertmanager_separate_probe_reason_from_runnable_checks() -> None:
    probe_component = read("app/templates/components/technical_probe.html")
    check_component = read("app/templates/components/technical_check.html")
    prometheus = read("app/templates/prometheus/partials/_detail_validation_content.html")
    alertmanager = read("app/templates/alertmanager/partials/_detail_validation_content.html")
    assert 'Why KAORI Checks This' in prometheus
    assert 'Why KAORI Checks This' in alertmanager
    assert 'navigator.clipboard' not in probe_component
    assert 'navigator.clipboard' in check_component
    assert "technical_check.render(check, query_label='Full PromQL Query')" in prometheus
    assert "technical_check.render(check, query_label='Full API Request')" in alertmanager
    prometheus_presentation = read("app/prometheus/presentation.py")
    alertmanager_presentation = read("app/alertmanager/presentation.py")
    assert 'Exact executable queries are available under Technical Checks.' in prometheus_presentation
    assert "'query': str(check.get('query') or '')" in prometheus_presentation
    assert 'Exact request targets are available under Technical Checks.' in alertmanager_presentation
    assert "'query': request_target" in alertmanager_presentation
