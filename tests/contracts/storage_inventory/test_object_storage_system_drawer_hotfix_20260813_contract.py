from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_system_drawer_alpine_expression_uses_json_safe_expression() -> None:
    template = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    assert "x_show='openDrawer === ' ~ (system.id|tojson)" in template
    assert 'x_show="openDrawer === \'" ~ system.id ~ "\'"' not in template
    assert "close_expression='openDrawer = null'" in template


def test_system_drawer_button_keeps_json_safe_assignment() -> None:
    template = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    assert "@click='openDrawer = {{ system.id|tojson }}'" in template
