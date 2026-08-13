from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_system_drawer_alpine_expression_uses_html_safe_string_literal() -> None:
    template = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    expected = 'x_show="openDrawer === \'" ~ system.id ~ "\'"'
    assert expected in template
    assert "x_show='openDrawer === ' ~ (system.id|tojson)" not in template
    assert "close_expression='openDrawer = null'" in template


def test_system_drawer_button_keeps_json_safe_assignment() -> None:
    template = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    assert "@click='openDrawer = {{ system.id|tojson }}'" in template


def test_drawer_visibility_and_button_assignment_use_compatible_literals() -> None:
    template = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    # The click assignment may safely use JSON because the HTML attribute itself uses single quotes.
    assert "@click='openDrawer = {{ system.id|tojson }}'" in template
    # side_drawer.render later emits x-show inside a double-quoted HTML attribute, so its
    # Alpine expression must use single quotes around the UUID instead of embedded JSON quotes.
    assert 'x_show="openDrawer === \'" ~ system.id ~ "\'"' in template
