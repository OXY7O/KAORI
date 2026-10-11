"""Role Detail unified evidence hierarchy and Roles overview copy contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_role_detail_modal_uses_one_full_width_resource_sheet() -> None:
    template = read('app/templates/access/roles/partials/_role_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')

    Environment().parse(template)
    assert 'data-resource-detail-header' in template
    assert 'data-kaori-detail-variant="full-workspace-modal"' in template
    assert 'data-kaori-detail-density="unified-resource-sheet"' in template
    assert 'detail_ui.header_identity_row()' in template
    assert 'detail_ui.summary_strip([' in template
    assert '], compact=true, borderless=true)' in template
    assert 'data-resource-detail-summary' in shared
    assert 'data-kaori-summary-variant="borderless"' in shared

    assert 'data-kaori-role-detail-layout="unified-resource-sheet"' in template
    assert 'detail_ui.resource_sheet()' in template
    assert 'data-kaori-unified-resource-sheet' in shared
    assert 'data-kaori-inventory-section-layout="resource-sheet-band"' in shared
    assert template.count('detail_ui.inventory_section(') == 4
    assert template.count('compact_layout=true') == 4
    assert 'detail_ui.detail_card(' not in template
    assert 'lg:grid-cols-2' not in template
    assert template.count('{% call ') == template.count('{% endcall %}')

    order = [
        "'Role Identity', 'badge-info'",
        "'Assignment Impact', 'users-round'",
        "'Permission Coverage', 'key-round'",
        "'Administrative Boundary', 'shield-check'",
    ]
    assert [template.index(part) for part in order] == sorted(
        template.index(part) for part in order
    )


def test_role_detail_long_evidence_has_full_width_reading_measures() -> None:
    template = read('app/templates/access/roles/partials/_role_detail.html')

    assert 'data-kaori-role-identity-facts' in template
    assert 'data-kaori-role-impact-facts' in template
    assert 'data-kaori-role-purpose' in template
    assert 'data-kaori-role-baseline' in template
    assert 'max-w-4xl break-words text-sm font-normal leading-6' in template
    assert 'max-w-4xl break-words text-sm leading-6 text-content-secondary' in template
    assert 'max-w-4xl text-sm leading-6 text-content-primary' in template
    assert 'lg:grid-cols-[minmax(0,1fr)_auto]' not in template
    assert 'grid min-w-0 gap-x-8 gap-y-3 sm:grid-cols-2' in template
    assert 'sm:grid-cols-3' in template  # short impact values only


def test_role_detail_permission_directory_keeps_every_capability_visible() -> None:
    template = read('app/templates/access/roles/partials/_role_detail.html')

    assert 'data-kaori-role-permission-coverage' in template
    assert 'aria-label="Role permission coverage by module"' in template
    assert '<ul class="min-w-0 divide-y divide-outline-subtle"' in template
    assert '<li class="grid min-w-0 gap-x-6 gap-y-3 py-3' in template
    assert 'sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]' in template
    assert 'data-kaori-role-module' in template
    assert 'module.count' in template
    assert 'aria-label="{{ module.count }} permission{{' in template
    assert 'detail.module_count' in template
    assert '{% for module in detail.permission_modules %}' in template
    assert '{% for permission in module.permissions %}' in template
    assert 'table_label.metadata_label(permission.label, wrap=true)' in template
    assert 'data-kaori-role-module-capabilities' in template
    assert '<table ' not in template  # no narrow three-column matrix
    assert '<details' not in template  # no hidden/partially presented evidence
    assert "detail_ui.empty_evidence('No Permissions Assigned'" in template



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
    assert 'data-kaori-role-actions' in template
    assert 'mt-4 flex flex-wrap items-center gap-2 border-t border-outline-subtle pt-3' in template
    assert 'can_manage_roles and detail.mutation_protected' in template
    assert 'can_mutate_role' in template
    assert 'Role assignments are evaluated on each protected authorization check.' not in template


def test_roles_overview_copy_matches_approved_refinement() -> None:
    page = read('app/templates/access/roles/index.html')

    assert 'Inactive roles fail closed on the next effective authorization check.' in page
    assert 'Protected defaults require RBAC review.' in page
    assert 'Inactive roles fail closed on the next authorization check.' not in page
    assert 'Protected default definitions requiring RBAC convergence review.' not in page
