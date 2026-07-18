from pathlib import Path

TEMPLATE_PATHS = (
    Path('app/templates/settings/roles/index.html'),
    Path('app/templates/settings/roles/form.html'),
    Path('app/templates/settings/permissions/index.html'),
)


def test_alpine_json_values_are_html_attribute_escaped():
    """Prevent JSON quotes from terminating Alpine HTML attributes early."""
    for template_path in TEMPLATE_PATHS:
        source = template_path.read_text(encoding='utf-8')
        unsafe_lines = [
            (line_number, line.strip())
            for line_number, line in enumerate(source.splitlines(), start=1)
            if 'tojson' in line and 'tojson|forceescape' not in line
        ]

        assert not unsafe_lines, (
            f'{template_path} contains Alpine/Jinja JSON without forceescape: '
            f'{unsafe_lines}'
        )


def test_role_permission_editor_does_not_depend_on_inline_alpine_state():
    source = Path('app/templates/settings/roles/form.html').read_text(encoding='utf-8')

    assert 'data-role-permission-editor' in source
    assert "js/role_permission_editor.js" in source
    assert 'x-data="{ search:' not in source
    assert '@change="sync()"' not in source
    assert 'document.querySelectorAll(`[data-role-permission]' not in source
