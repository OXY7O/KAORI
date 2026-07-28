from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_page_and_table_filters_do_not_listen_to_controls_outside_their_form():
    page = read("app/templates/analytics/alerts/index.html")
    table = read("app/templates/analytics/alerts/partials/_table_filters.html")

    assert "from:select" not in page
    assert "from:select" not in table
    assert "from:input" not in page
    assert "from:input" not in table
    assert "event.target.matches('select')" in page
    assert "event.target.matches('select')" in table
    assert "event.target.name === 'search'" not in page
    assert "event.target.name === 'search'" in table


def test_search_icon_uses_intrinsic_vertical_centering():
    page_filters = read("app/templates/analytics/alerts/partials/_filters.html")
    table_filters = read("app/templates/analytics/alerts/partials/_table_filters.html")

    assert 'name="search"' not in page_filters
    assert "absolute inset-y-0 left-0 flex items-center pl-3" in table_filters
    assert "top-[35px]" not in table_filters
    assert "top-[37px]" not in table_filters


def test_table_filter_keeps_local_fragment_and_loading_boundaries():
    template = read("app/templates/analytics/alerts/partials/_table_filters.html")

    assert 'hx-target="{{ target_id }}"' in template
    assert 'hx-sync="{{ target_id }}:replace"' in template
    assert 'hx-indicator="#{{ indicator_id }}"' in template
    assert 'name="page" value="1"' in template
