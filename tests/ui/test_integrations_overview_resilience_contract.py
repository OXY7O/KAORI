from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/integrations/service.py"
RUNTIME = ROOT / "app/templates/integrations/partials/_runtime_overview.html"
OVERVIEW = ROOT / "app/templates/integrations/overview.html"
DOC = ROOT / "docs/modules/integrations/UI_REFERENCE.md"
AUDIT = ROOT / "docs/design/audits/INTEGRATIONS_OVERVIEW_RESILIENCE_AUDIT_2026_07.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def overview_builder_source() -> str:
    source = read(SERVICE)
    start = source.index("def build_integrations_overview(")
    end = source.index("\ndef build_kubernetes_page", start)
    return source[start:end]


def test_overview_builder_uses_provider_native_persisted_records() -> None:
    source = overview_builder_source()
    assert "KubernetesConnection.query" in source
    assert "PrometheusInstance.query" in source
    assert "AlertmanagerInstance.query" in source
    assert "resolve_instance_for_cluster" not in source
    assert "resolve_alertmanager_sources" not in source
    assert "runtime_has_targets" in source
    assert "runtime_has_active_filters" in source


def test_runtime_navigation_does_not_execute_dynamic_endpoint_names() -> None:
    source = read(RUNTIME)
    assert "url_for(row.detail_endpoint" not in source
    assert "row.detail_kwargs" not in source
    assert "url_for('integrations.kubernetes_detail'" in source
    assert "url_for('prometheus.instance_detail'" in source
    assert "url_for('alertmanager.instance_detail'" in source
    assert "Unavailable" in source


def test_zero_target_and_filtered_zero_states_are_distinct() -> None:
    source = read(RUNTIME)
    assert "No Runtime Targets Yet" in source
    assert "No Runtime Targets Match These Filters" in source
    assert source.index("{% if not runtime_has_targets %}") < source.index("No Runtime Targets Yet")
    assert "live provider access is not required to open this page" in source


def test_coverage_includes_kubernetes_domain() -> None:
    service = read(SERVICE)
    overview = read(OVERVIEW)
    assert "'label': 'Compute & Infrastructure'" in service
    assert "md:grid-cols-2 xl:grid-cols-4" in overview


def test_resilience_boundary_is_documented_and_audited() -> None:
    doc = read(DOC)
    audit = read(AUDIT)
    assert "provider resolver decision" in doc
    assert "An empty provider inventory is a normal product state" in doc
    assert "dynamic runtime endpoints are absent" in audit
    assert "persistence-only boundary" in audit
