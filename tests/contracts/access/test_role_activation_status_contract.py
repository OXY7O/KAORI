"""Role activation preview must reflect the form, not a hardcoded Active badge."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def test_role_form_status_preview_is_data_driven() -> None:
    form = (ROOT / 'app/templates/access/roles/form.html').read_text(encoding='utf-8')
    js = (ROOT / 'app/static/js/role_permission_editor.js').read_text(encoding='utf-8')

    Environment().parse(form)
    assert "macro role_state_badge(active_label, inactive_label)" in form
    assert "if not form.is_active.data" in form
    assert "if form.is_active.data" in form
    assert "role_state_badge('Active Role' if read_only else 'Active on Save'" in form
    assert "role_state_badge('Active' if read_only else 'Active on Save'" in form
    assert "'Inactive Role' if read_only else 'Inactive on Save'" in form
    assert 'data-role-state-active' in form
    assert 'data-role-state-inactive' in form
    assert 'aria-live="polite"' in form
    assert "table_label.status_label('Active Role', 'normal', 'circle-check')" not in form
    assert "root.querySelector('input[name=\"is_active\"]')" in js
    assert "roleActiveCheckbox?.addEventListener('change', syncRoleStatusPreview)" in js
    assert "el.hidden = !roleActiveCheckbox.checked" in js
    assert "el.hidden = roleActiveCheckbox.checked" in js
