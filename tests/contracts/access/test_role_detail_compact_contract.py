"""Role Detail compact evidence hierarchy and Roles overview copy contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_role_detail_modal_preserves_host_and_uses_compact_evidence() -> None:
    template = read('app/templates/access/roles/partials/_role_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')

    Environment().parse(template)
    assert 'data-resource-detail-header' in template
    assert 'data-kaori-detail-variant="full-workspace-modal"' in template
    assert 'detail_ui.header_identity_row()' in template
    assert 'detail_ui.summary_strip([' in template
    assert '], compact=true, borderless=true)' in template
    assert 'data-resource-detail-summary' in shared
    assert 'data-kaori-summary-variant="borderless"' in shared
    assert 'data-kaori-role-detail-layout="compact-evidence"' in template
    assert 'lg:grid-cols-2' in template
    assert 'data-kaori-role-identity-facts' in template
    assert 'data-kaori-role-impact-facts' in template
    assert 'data-kaori-role-permission-coverage' in template
    assert 'data-kaori-role-administrative-boundary' in template
    assert template.count("detail_ui.detail_card(") == 4
    assert "table_ui.table_classes('min-w-[42rem]')" in template
    assert 'aria-label="Role permission coverage by module"' in template
    assert 'data-kaori-role-module-capabilities' in template
    assert 'flex min-w-0 flex-wrap gap-1' in template

    order = [
        "detail_ui.detail_card('Role Identity'",
        "detail_ui.detail_card('Assignment Impact'",
        "detail_ui.detail_card('Permission Coverage'",
        "detail_ui.detail_card('Administrative Boundary'",
    ]
    assert [template.index(part) for part in order] == sorted(template.index(part) for part in order)
    assert template.count('{% call ') == template.count('{% endcall %}')


def test_role_detail_preserves_committed_evidence_and_mutation_guards() -> None:
    template = read('app/templates/access/roles/partials/_role_detail.html')

    for evidence in (
        'role.display_name',
        'role.name',
        'detail.type_label',
        'detail.state_label',
        'detail.baseline_label',
        'detail.baseline_detail',
        "role.description or 'No role description is defined.'",
        'detail.assigned_users',
        'detail.provider_mappings',
        'detail.assignment_effect',
        'detail.permission_modules',
        'module.permissions',
        'module.count',
        'detail.delete_blocked and not detail.mutation_protected',
        'detail.within_delegation',
        'detail.delete_eligible',
        'data-destructive-modal-open',
        "url_for('access.roles.detail', role_id=role.id)",
        "url_for('access.roles.clone', role_id=role.id)",
        "url_for('access.roles.edit', role_id=role.id)",
        "url_for('access.roles.delete', role_id=role.id)",
        'csrf_token()',
        'detail.version_token',
    ):
        assert evidence in template
    assert 'can_manage_roles and detail.mutation_protected' in template
    assert 'can_mutate_role' in template
    assert 'Role assignments are evaluated on each protected authorization check.' not in template


def test_roles_overview_copy_matches_approved_refinement() -> None:
    page = read('app/templates/access/roles/index.html')

    assert 'Inactive roles fail closed on the next effective authorization check.' in page
    assert 'Protected defaults require RBAC review.' in page
    assert 'Inactive roles fail closed on the next authorization check.' not in page
    assert 'Protected default definitions requiring RBAC convergence review.' not in page
