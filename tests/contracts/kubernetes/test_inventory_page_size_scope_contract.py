from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_resource_filter_forms_only_listen_to_their_own_controls() -> None:
    for resource in ('nodes', 'namespaces', 'workloads'):
        template = read(f'app/templates/inventory/kubernetes/{resource}/partials/_table_card.html')
        assert 'hx-trigger="change, keyup changed delay:500ms from:find input[name=\'search\']"' in template
        assert 'change from:select' not in template


def test_page_size_changes_refresh_only_the_canonical_table_content() -> None:
    for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage'):
        template = read(f'app/templates/inventory/kubernetes/{resource}/partials/_table_content.html')
        form_start = template.index('<form hx-get=')
        form_end = template.index('</form>', form_start)
        page_size_form = template[form_start:form_end]
        assert f'hx-target="#{resource}-table-content"' in page_size_form
        assert 'hx-swap="innerHTML"' in page_size_form
        assert 'name="partial_mode" value="table_content"' in page_size_form
        assert 'name="page" value="1"' in page_size_form
        assert 'name="per_page"' in page_size_form
