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


def test_role_permission_checkbox_stays_inside_its_card_viewport():
    template_source = Path('app/templates/settings/roles/form.html').read_text(encoding='utf-8')
    editor_source = Path('app/static/js/role_permission_editor.js').read_text(encoding='utf-8')

    assert 'group relative flex min-h-20' in template_source
    assert 'class="peer sr-only"' not in template_source
    assert 'peer absolute left-3 top-3 z-10 h-8 w-8' in template_source
    assert 'peer-focus-visible:ring-2' in template_source
    assert 'function repairDocumentViewport()' in editor_source
    assert "window.scrollTo({ left: 0, top: 0, behavior: 'auto' })" in editor_source
    assert "root.addEventListener('focusin'" in editor_source


def test_role_permission_matrix_is_solid_and_modules_are_closed_by_default():
    source = Path('app/templates/settings/roles/form.html').read_text(encoding='utf-8')

    assert 'grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]' in source
    assert 'class="min-w-0 self-start space-y-6"' in source
    assert 'data-role-permission-matrix' in source

    matrix_position = source.index('data-role-permission-matrix')
    matrix_tag_start = source.rfind('<section', 0, matrix_position)
    matrix_tag_end = source.index('>', matrix_position)
    assert matrix_tag_start >= 0
    assert '<details' not in source[matrix_tag_start:matrix_tag_end]
    assert '<summary' not in source[matrix_tag_start:source.index('data-role-module-toggle-all')]
    assert 'RBAC scope' in source[matrix_tag_start:source.index('data-role-module-toggle-all')]

    assert source.index('Role configuration') < matrix_position < source.index('<aside class="self-start space-y-5">')
    assert 'data-role-module-toggle-all' in source
    assert 'data-role-module-toggle-all-label>Expand all<' in source
    assert 'data-expanded="false"' in source
    assert 'data-role-module-content' in source
    module_content_position = source.index('data-role-module-content')
    assert 'hidden' in source[module_content_position:module_content_position + 180]
