from pathlib import Path
import re


ANALYTICS_ROOT = Path("app/templates/analytics")
RAW_GUIDANCE_PATTERN = re.compile(
    r">\s*(How To Read|What To Do|What To Watch|Operational Reading|Recommended Action|Recommended Review Path|Forecast Decision|Operational Guidance)\s*<",
    re.IGNORECASE,
)


def test_analysis_surface_owns_role_based_guidance_geometry_and_palette():
    surface = (ANALYTICS_ROOT / "components/_analysis_surfaces.html").read_text()
    assert "macro role_icon_classes(role='brand', tone='info', size='default')" in surface
    assert "macro role_label_classes(role='brand', tone='info')" in surface
    assert "macro guidance_icon_classes(role='brand', tone='info', size='default')" in surface
    assert "macro interpretation_content" in surface
    assert "macro interpretation_callout" in surface
    assert "role='brand'" in surface
    assert "border-kaori-border bg-kaori-soft text-kaori-primary" in surface
    assert "table_label.tone_border_classes('info')" in surface
    assert "table_label.tone_surface_classes('info')" in surface
    assert "table_label.tone_icon_classes('info')" in surface
    assert "table_label.tone_surface_classes(resolved_tone)" in surface
    assert "text-content-secondary" in surface
    assert "semantic=false" not in surface


def test_analytics_templates_do_not_recreate_guidance_labels_as_raw_markup():
    violations = []
    for template in ANALYTICS_ROOT.rglob("*.html"):
        if template.name == "_analysis_surfaces.html":
            continue
        content = template.read_text()
        if RAW_GUIDANCE_PATTERN.search(content):
            violations.append(str(template))
    assert violations == []


def test_every_analytics_domain_uses_shared_guidance_callouts():
    expected = {
        "overview": "overview/partials/_capacity_snapshot.html",
        "utilization": "utilization/partials/_current_summary.html",
        "capacity": "capacity/partials/_allocation.html",
        "storage": "storage/partials/_capacity_utilization_panel.html",
        "workload": "workload/partials/_overview.html",
        "forecast": "forecast/partials/_forecast_section.html",
        "top_consumers": "top_consumers/partials/_top_consumers_section.html",
        "alerts": "alerts/partials/_cluster_signal_overview.html",
    }
    for domain, relative in expected.items():
        content = (ANALYTICS_ROOT / relative).read_text()
        assert "interpretation_" in content, domain
        assert "role=" in content, domain


def test_record_level_guidance_uses_compact_shared_variant():
    record_templates = [
        "workload/partials/_tenant_quota_section.html",
        "workload/partials/_workload_mapping_section.html",
        "top_consumers/partials/_consumer_detail_results.html",
        "alerts/partials/_anomalies_table_row.html",
        "storage/partials/_persistent_volumes_panel.html",
    ]
    for relative in record_templates:
        content = (ANALYTICS_ROOT / relative).read_text()
        assert "interpretation_callout(" in content, relative
        assert ("compact=true" in content or "card=true" in content), relative
        assert "role=" in content, relative
