from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_alertmanager_runtime_identity_precedes_version() -> None:
    source = read("app/templates/integrations/alertmanager/partials/_inventory_content.html")
    runtime = source[source.index('<td class="px-4 py-4 align-top">', source.index('row.instance.description')):]
    runtime = runtime[:runtime.index('</td>')]
    assert runtime.index('row.deployment_type') < runtime.index('row.version')
    assert "Version not detected" in runtime


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


def test_prometheus_and_alertmanager_use_non_copyable_technical_probe_values() -> None:
    component = read("app/templates/components/technical_probe.html")
    prometheus = read("app/templates/prometheus/partials/_detail_validation_content.html")
    alertmanager = read("app/templates/alertmanager/partials/_detail_validation_content.html")
    assert 'bg-kaori-soft' in component
    assert 'navigator.clipboard' not in component
    assert "technical_probe.render(row.probe, label='Technical Probe')" in prometheus
    assert "technical_probe.render(row.probe, label='Technical Probe')" in alertmanager
