from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_resource_filter_forms_only_listen_to_their_own_controls() -> None:
    for resource in ("nodes", "namespaces", "workloads"):
        template = read(f"app/templates/inventory/{resource}/partials/_table_card.html")
        assert 'hx-trigger="change, keyup changed delay:500ms from:find input[name=\'search\']"' in template
        assert "change from:select" not in template


def test_page_size_changes_refresh_the_owning_inventory_scope() -> None:
    targets = {
        "nodes": "#nodes-inventory-scope",
        "namespaces": "#namespaces-inventory-scope",
        "workloads": "#workloads-inventory-scope",
    }
    for resource, target in targets.items():
        template = read(f"app/templates/inventory/{resource}/partials/_table_content.html")
        form_start = template.index("<form hx-get=")
        form_end = template.index("</form>", form_start)
        page_size_form = template[form_start:form_end]
        assert f'hx-target="{target}"' in page_size_form
        assert 'hx-swap="outerHTML"' in page_size_form
        assert 'name="page" value="1"' in page_size_form
        assert 'name="per_page"' in page_size_form
