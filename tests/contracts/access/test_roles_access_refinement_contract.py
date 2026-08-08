from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_roles_access_registry_uses_kaori_workspace_and_table_standard() -> None:
    index = read('app/templates/access/roles/index.html')
    registry = read('app/templates/access/roles/partials/_registry.html')

    for required in (
        'Role Registry Overview',
        'Role Assignment Flow',
        'components/page_hero.html',
        'components/operational_section_card.html',
        'components/operational_point_flow.html',
        'access/roles/partials/_registry.html',
    ):
        assert required in index

    for required in (
        'components/table.html',
        'components/table_label.html',
        'components/loading_bar.html',
        'components/pagination.html',
        'components/details/_expandable_row.html',
        'Search Role',
        'Role Type',
        'Role State',
        'Refreshing Role Registry',
        'Rows',
        'Previous',
        'Next',
        'View Details',
    ):
        assert required in registry

    assert 'Role-Permission Mapping Matrix' not in index
    assert 'role_access_tabs.js' not in index
    assert 'data-role-matrix' not in index


def test_roles_access_detail_exposes_assignment_and_delete_boundaries() -> None:
    detail = read('app/templates/access/roles/partials/_role_detail.html')
    for required in (
        'Assignment Impact',
        'Provider Defaults',
        'Permission Coverage',
        'Administrative Boundary',
        'Protected defaults are code-owned',
        'data-destructive-modal-open',
        'role_version',
    ):
        assert required in detail


def test_role_mutations_are_serialized_and_version_checked() -> None:
    service = read('app/access/roles/service.py')
    routes = read('app/access/roles/routes.py')
    forms = read('app/access/roles/forms.py')

    assert 'with_for_update()' in service
    assert '.populate_existing()' in service
    assert "db.session.expire(role, ['permissions'])" in service
    assert 'def role_version_token' in service
    assert 'def role_version_matches' in service
    assert 'lock_role_for_mutation(role_id)' in routes
    assert "This role changed after the page was opened" in routes
    assert "The role changed after the registry was loaded" in routes
    assert 'role_version = HiddenField' in forms


def test_role_form_uses_sticky_impact_rail_and_dependency_evidence() -> None:
    form = read('app/templates/access/roles/form.html')
    for required in (
        'Role Impact',
        'Provider Defaults',
        'xl:sticky xl:top-5',
        "table_label.status_label('Required'",
        'Access Guardrails',
        'next authorization check',
    ):
        assert required in form


def test_obsolete_role_access_tab_script_is_removed() -> None:
    assert not (ROOT / 'app/static/js/role_access_tabs.js').exists()


def test_role_registry_uses_canonical_pagination_page_size_macro() -> None:
    template = read('app/templates/access/roles/partials/_registry.html')
    assert 'pagination_ui.page_size_classes()' in template
    assert 'pagination_ui.select_classes()' not in template
