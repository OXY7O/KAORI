from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_permission_governance_intro_is_outside_tab_workspace() -> None:
    page = read('app/templates/access/permissions/index.html')
    workspace = read('app/templates/access/permissions/partials/_workspace.html')
    assert '{% import "components/section_intro.html" as section_intro %}' in page
    assert "'Permission Governance'" in page
    assert 'Explore code-owned permission contracts, registry alignment, and role coverage.' in page
    assert page.index("'Permission Governance'") < page.index(
        '{% include "access/permissions/partials/_workspace.html" %}'
    )
    assert 'section_intro.render(' not in workspace
    assert 'id="permission-workspace"' in workspace
    assert "'Permission Registry'" in workspace
    assert "'Role Coverage'" in workspace


def test_role_flow_and_registry_each_have_a_distinct_section_intro() -> None:
    page = read('app/templates/access/roles/index.html')
    registry = read('app/templates/access/roles/partials/_registry.html')
    assert page.count('section_intro.render(') == 2
    assert "'Authorization Flow'" in page
    assert "'Role Administration'" in page
    assert (
        page.index("'Authorization Flow'")
        < page.index("'Role Assignment Flow'")
        < page.index("'Role Administration'")
        < page.index('{% include "access/roles/partials/_registry.html" %}')
    )
    assert 'Role Registry' in registry
    assert 'id="role-registry"' in registry
    assert 'section_intro.render(' not in registry


def test_user_directory_intro_is_in_full_content_not_htmx_directory_fragment() -> None:
    content = read('app/templates/access/users/partials/_content.html')
    directory = read('app/templates/access/users/partials/_directory.html')
    routes = read('app/access/users/routes.py')
    assert "'Account Directory'" in content
    assert "'Find users by identity source, account state, and role assignment.'" in content
    assert content.index("'Account Directory'") < content.index('{% include "access/users/partials/_directory.html" %}')
    assert 'section_intro.render(' not in directory
    assert 'id="user-directory"' in directory
    assert 'User Directory' in directory
    assert "request.headers.get('HX-Target') == 'user-directory'" in routes
    assert "render_template('access/users/partials/_directory.html', **payload)" in routes


def test_shared_intro_preserves_access_read_only_and_existing_card_titles() -> None:
    shared = read('app/templates/components/section_intro.html')
    assert '{% macro render(' in shared
    assert 'text-lg font-semibold text-content-primary' in shared
    assert 'text-sm leading-6 text-content-secondary' in shared
    permission = read('app/templates/access/permissions/partials/_registry.html')
    flow = read('app/templates/access/roles/index.html')
    directory = read('app/templates/access/users/partials/_directory.html')
    assert '>Permission Registry</h2>' in permission
    assert "'Role Assignment Flow'" in flow
    assert '>User Directory</h2>' in directory
    for text in (permission, flow, directory):
        assert 'hx-post=' not in text



def test_access_boundaries_uses_authorization_flow_external_intro_pattern() -> None:
    overview = read('app/templates/access/overview/index.html')
    roles = read('app/templates/access/roles/index.html')
    assert "section_intro.render('Authorization Flow'," in roles
    assert "section_intro.render('Access Boundaries'," in overview
    assert "id='access-boundaries-heading'" in overview
    assert 'aria-labelledby="access-boundaries-heading"' in overview
    assert 'operational_section.shell_classes()' in overview
    assert overview.index("section_intro.render('Access Boundaries'") < overview.index(
        'aria-labelledby="access-boundaries-heading"'
    )
