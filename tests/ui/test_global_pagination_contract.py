from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_pagination_document_is_indexed() -> None:
    index = read("docs/design/README.md")
    standard = read("docs/design/components/PAGINATION.md")
    assert "components/PAGINATION.md" in index
    assert "Showing {start}–{end} of {total} {resource}" in standard
    assert "Default page size: `5`" in standard
    assert "`5`, `10`, `25`, and `50`" in standard


def test_shared_analytics_default_page_size_is_five() -> None:
    params = read("app/analytics/common/params.py")
    base = read("app/analytics/common/base_service.py")
    workload = read("app/analytics/workload/service.py")
    assert "default: int = 5" in params
    assert "default_per_page: int = 5" in base
    assert "default_per_page=5" in workload


def test_integrations_runtime_summary_names_its_resource() -> None:
    template = read("app/templates/integrations/partials/_runtime_overview.html")
    assert "integration target" in template
    assert "integration targets" in template
    assert ">Rows per page<" not in template
    assert 'aria-label="Integration targets per page"' in template
    assert template.index('aria-label="Integration targets per page"') < template.index("{% if runtime_pagination.has_prev %}")


def test_users_summary_uses_global_wording() -> None:
    template = read("app/templates/users/partials/_table.html")
    assert "Showing {{ pagination.start_item }}–{{ pagination.end_item }}" in template
    assert "matching user accounts" not in template
    assert "Viewing {{ pagination.start_item }}" not in template


def test_alerts_empty_state_keeps_stable_pagination_summary() -> None:
    template = read("app/templates/analytics/alerts/partials/_pagination.html")
    assert "pagination.start_item if pagination.total_items else 0" in template
    assert "pagination.end_item if pagination.total_items else 0" in template
    assert ">Rows per page<" not in template
    assert "per page" in template
    assert "No {{ row_label" not in template


def test_inventory_resource_labels_use_sentence_style() -> None:
    pods = read("app/templates/inventory/pods/partials/_table_content.html")
    services = read("app/templates/inventory/services/partials/_table_content.html")
    ingresses = read("app/templates/inventory/ingresses/partials/_table_content.html")
    assert "'pod'" in pods and "'pods'" in pods
    assert "'service'" in services and "'services'" in services
    assert "'ingress'" in ingresses and "'ingresses'" in ingresses
