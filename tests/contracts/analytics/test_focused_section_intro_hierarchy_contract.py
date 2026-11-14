"""#4761: focused Analytics section-intro hierarchy and compact operator copy."""

from pathlib import Path

from jinja2 import Environment

TEMPLATES = Path("app/templates/kubernetes/analytics")
CAPACITY = Path("app/kubernetes/analytics/capacity")
FOCUSED = {
    "utilization": ("_overview.html", "utilization-content"),
    "capacity": ("_overview.html", "capacity-content"),
    "workload": ("_overview.html", "workload-content"),
    "storage": ("_overview.html", "storage-content"),
    "top_consumers": ("_summary.html", "top-consumers-content"),
    "forecast": ("_overview_methodology.html", "forecast-content"),
    "alerts": ("_cluster_signal_overview.html", "alerts-content"),
}
POSTURE_NAMES = {
    "utilization": "Review Utilization Posture",
    "capacity": "Review Capacity Posture",
    "workload": "Review Workload Posture",
    "storage": "Review Storage Posture",
    "top_consumers": "Review Consumer Posture",
    "forecast": "Review Forecast Posture",
    "alerts": "Review Signal Posture",
}
DOMAIN_NAMES = {
    "utilization": "Explore Utilization Domains",
    "capacity": "Explore Capacity Domains",
    "workload": "Explore Workload Domains",
    "storage": "Explore Storage Domains",
    "top_consumers": "Explore Consumer Domains",
    "forecast": "Explore Forecast Domains",
    "alerts": "Explore Alert Domains",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_seven_focused_pages_reuse_two_plain_section_intros_in_order() -> None:
    """Two contextual introductions precede existing cards and tab shells."""
    environment = Environment(autoescape=True)
    for domain, (summary, _) in FOCUSED.items():
        page = read(TEMPLATES / domain / "index.html")
        environment.parse(page)

        heading = f"analytics-{domain}-posture-heading"
        domains_heading = f"analytics-{domain}-domains-heading"
        overview = f'kubernetes/analytics/{domain}/partials/{summary}'
        assert 'components/section_intro.html" as section_intro' in page
        assert page.count("section_intro.render(") == 2, domain
        assert page.count('<section class="space-y-4"') == 2, domain
        assert page.count(f'aria-labelledby="{heading}"') == 1, domain
        assert page.count(f'aria-labelledby="{domains_heading}"') == 1, domain
        assert page.count(f"'{heading}'") == 1, domain
        assert page.count(f"'{domains_heading}'") == 1, domain
        assert f"'{POSTURE_NAMES[domain]}'" in page
        assert f"'{DOMAIN_NAMES[domain]}'" in page
        assert page.index("section_intro.render(") < page.index(overview)
        assert page.index(overview) < page.index(domains_heading)
        assert page.index(domains_heading) < page.index("section_intro.render(", page.index(overview))

    assert len(set(POSTURE_NAMES.values())) == len(FOCUSED)
    assert len(set(DOMAIN_NAMES.values())) == len(FOCUSED)


def test_focused_intros_preserve_tab_ownership_and_existing_guide_surfaces() -> None:
    for domain, (_, tabset) in FOCUSED.items():
        page = read(TEMPLATES / domain / "index.html")
        assert page.count("section_intro.render(") == 2
        assert "kaori-analytics-page space-y-6" in page
        assert "dependency_blocker" in page
        if domain in {"storage", "forecast", "top_consumers"}:
            assert f'kubernetes/analytics/{domain}/partials/' in page
        else:
            assert page.count("analytics_workspace.tabbed(") == 1
            assert page.count("{% endcall %}") == 1
            assert f"'{tabset}'" in page
        if domain in {"utilization", "capacity", "workload", "alerts"}:
            assert "title_accessory=info_tip.render(" in page

    usage = read(TEMPLATES / "utilization/index.html")
    workload = read(TEMPLATES / "workload/index.html")
    alerts = read(TEMPLATES / "alerts/index.html")
    assert usage.count('hx-trigger="kaori:analytics-tab-activated once"') == 2
    assert workload.count('hx-trigger="kaori:analytics-tab-activated once"') == 2
    assert "data-analytics-preserve-tab" in alerts
    assert "alerts-control-form" in alerts


def test_concise_guidance_preserves_filesystem_authority_and_interpretations() -> None:
    trend = read(TEMPLATES / "utilization/partials/_trend.html")
    capacity_overview = read(TEMPLATES / "capacity/partials/_overview.html")
    capacity_allocation = read(TEMPLATES / "capacity/partials/_allocation.html")
    domain = read(CAPACITY / "domain.py")
    presentation = read(CAPACITY / "presentation.py")

    concise_trend = (
        "Investigate sustained pressure across the selected window. "
        "Use Node Detail to confirm hotspots and assess redistribution before resizing."
    )
    old_filesystem = "Operational node-filesystem reference; not Kubernetes allocatable capacity"
    short_filesystem = "Filesystem: not Kubernetes allocatable."

    assert concise_trend in trend
    assert len(concise_trend) <= 145
    assert trend.count("analysis_surface.interpretation_callout(") == 2
    assert "How To Read" in trend and "What To Do" in trend
    assert "scope_label" in capacity_overview
    assert "item.scope_label" in capacity_allocation
    assert f"'scope_label': '{short_filesystem}'" in domain
    assert f"return '{short_filesystem}'" in presentation
    assert f"scope_label == '{old_filesystem}'" in presentation
    assert "'scope_label': scope_label" in presentation
    assert "'scheduling_resource': False" in domain
    assert "_SCHEDULING_RESOURCES = ('cpu', 'memory', 'pods')" in presentation
    assert "analysis_surface.interpretation_grid_classes(" in capacity_allocation
