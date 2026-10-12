"""Canonical KAORI table Results badges; source-only review contract (#1675)."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


TEMPLATES = Path(__file__).resolve().parents[3] / "app" / "templates"


def _template(path: str) -> str:
    return (TEMPLATES / path).read_text(encoding="utf-8")


def test_shared_result_count_badge_pluralization_and_missing_evidence() -> None:
    template = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True).get_template(
        "components/table_label.html"
    )
    counter = template.module.result_count
    zero = str(counter(0))
    one = str(counter(1))
    three = str(counter(3))
    assert "0 Results" in zero
    assert "1 Result" in one and "1 Results" not in one
    assert "3 Results" in three
    assert 'data-lucide="list-filter"' in three
    assert "kaori-semantic-label" in three and "bg-kaori-soft" in three
    assert str(counter(None)).strip() == ""


def test_shared_block_header_accepts_count_without_replacing_info_tip_or_actions() -> None:
    content = _template("components/table.html")
    assert "title_extra='', result_count=none" in content
    assert "{% if title_extra %}{{ title_extra }}{% endif %}" in content
    assert "{% if result_count is not none %}{{ table_label.result_count(result_count) }}{% endif %}" in content
    assert 'class="flex min-h-6 flex-wrap items-center gap-1.5"' in content
    assert "data-kaori-table-header-actions" in content


def test_inventory_and_tenant_results_use_filtered_total_not_visible_rows() -> None:
    inventory = (
        "configuration", "ingresses", "namespaces", "nodes",
        "pods", "services", "storage", "workloads",
    )
    for resource in inventory:
        content = _template(f"kubernetes/inventory/{resource}/partials/_table_card.html")
        assert "result_count=pagination.total_items" in content

    for resource in ("systems", "buckets"):
        content = _template(f"storage/object_storage/inventory/{resource}/partials/_table_card.html")
        assert "result_count=inventory.pagination.total_items" in content

    counts = {
        "_tenant_registry.html": "tenant_pagination",
        "_namespace_registry.html": "namespace_pagination",
        "_resource_profile_registry.html": "profile_pagination",
        "_group_registry.html": "group_pagination",
        "_membership_registry.html": "membership_pagination",
        "_credential_registry.html": "credential_pagination",
        "_access_grant_registry.html": "access_grant_pagination",
        "_namespace_access_registry.html": "namespace_access_pagination",
    }
    for name, pagination in counts.items():
        content = _template(f"kubernetes/tenant/partials/{name}")
        assert f"result_count={pagination}.total_items" in content


def test_registry_inventory_has_only_one_shared_result_badge() -> None:
    content = _template("artifact_registry/partials/_inventory_workspace.html")
    assert "result_count=inventory.total" in content
    assert "title_extra=registry_title_tip" in content
    assert "registry_title_tip ~ result_badge" not in content
    assert "{% set result_badge %}" not in content


def test_other_domain_tables_reuse_same_badge() -> None:
    sources = {
        "access/roles/partials/_registry.html": "summary.matching",
        "access/permissions/partials/_registry.html": "matching_count",
        "access/identity_providers/partials/_registry.html": "summary.matching",
        "access/activity_audit/partials/_activity_table_card.html": "pagination.total",
        "reports/generated/index.html": "payload.pagination.total_items",
        "reports/report_templates/index.html": "payload.pagination.total_items",
        "reports/schedules/index.html": "payload.run_pagination.total_items",
        "platform_operations/jobs/executions/partials/_registry.html": "job_pagination.total_items",
        "kubernetes/governance/tls_certificates/partials/_table.html": "payload.pagination.total_items",
        "integrations/components/_asset_owner_observability_sources.html": "visible_total",
    }
    for path, count_expr in sources.items():
        assert f"table_label.result_count({count_expr})" in _template(path) or (
            f"result_count={count_expr}" in _template(path)
        )


def test_connection_registry_shared_header_preserves_filter_actions() -> None:
    header = _template("integrations/components/_provider_registry.html")
    assert "action_html='', result_count=none" in header
    assert "table_label.result_count(result_count)" in header
    assert "if action_html" in header

    for path in (
        "integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html",
        "integrations/storage/object_storage/providers/minio/partials/_registry.html",
        "integrations/registry/providers/harbor/partials/_registry.html",
    ):
        assert "result_count=pagination.total_items" in _template(path)
