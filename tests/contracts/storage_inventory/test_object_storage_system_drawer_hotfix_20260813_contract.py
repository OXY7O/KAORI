from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_system_drawer_alpine_expression_uses_html_safe_string_literal():
    template = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    expected = 'x_show="openDrawer === \'" ~ system.id ~ "\'"'
    assert expected in template
    assert "close_expression='openDrawer = null'" in template


def test_system_drawer_open_button_serializes_uuid_value():
    template = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    assert "@click='openDrawer = {{ system.id|tojson }}'" in template
