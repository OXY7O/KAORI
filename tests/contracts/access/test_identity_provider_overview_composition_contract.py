"""Identity Providers Overview uses canonical KAORI Access composition contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_posture_has_compact_metrics_and_explicit_configuration_evidence() -> None:
    overview = read('app/templates/access/identity_providers/partials/_overview.html')
    Environment().parse(overview)

    assert "operational_section.render(" in overview
    assert "'Authentication Source Posture'" in overview
    assert "table_label.status_indicator_label(summary.posture_label, summary.posture_tone)" in overview
    assert 'data-kaori-idp-overview-metrics' in overview
    assert 'data-kaori-idp-posture-metric' in overview
    assert 'sm:grid-cols-2' in overview
    assert 'xl:grid-cols-4' in overview
    assert 'divide-x' not in overview
    assert 'gap-px bg-outline-subtle' not in overview

    for evidence in (
        'summary.configured',
        'summary.enabled',
        'summary.directory',
        'summary.sso',
        'summary.total == 0',
        'Configured means the adapter contract is complete',
        'it does not mean the connection was tested',
    ):
        assert evidence in overview

    assert 'data-kaori-idp-posture-context' in overview


def test_governance_preserves_four_distinct_authority_boundaries() -> None:
    overview = read('app/templates/access/identity_providers/partials/_overview.html')

    assert "'Identity Governance'" in overview
    assert 'data-kaori-idp-governance-boundaries' in overview
    assert 'data-kaori-idp-governance-item' in overview
    assert 'md:grid-cols-2' in overview
    for contract in (
        'Provider / Adapter Boundary',
        'Credential Ownership',
        'Identity Projection',
        'Authorization Boundary',
    ):
        assert contract in overview
    assert 'providers identify external identity authorities' in overview.lower()
    assert 'credential values remain external' in overview.lower()
    assert 'active kaori roles and account lifecycle state determine access' in overview.lower()


def test_directory_workflow_keeps_projection_and_permission_scopes() -> None:
    directory = read(
        'app/templates/access/identity_providers/partials/_directory_provisioning_strip.html'
    )
    Environment().parse(directory)

    assert "current_user.has_permission('identity_providers.provision')" in directory
    assert "action_href=url_for('identity_providers.directory_provisioning') if can_provision else none" in directory
    assert "header_badge=table_label.status_indicator_label('Read Only', 'unknown') if not can_provision else none" in directory
    assert 'summary.directory' in directory
    assert 'summary.directory_identity_links' in directory
    for title in ('Directory Providers', 'Identity Links', 'Authorization Owner'):
        assert title in directory
    assert 'KAORI Roles' in directory
    assert 'data-kaori-idp-directory-flow' in directory
    assert 'sm:grid-cols-2 lg:grid-cols-3' in directory
    assert 'provider-owned' in directory
    assert 'credentials remain external' in directory.lower()


def test_server_owned_framed_navigation_does_not_change_route_authority() -> None:
    tabs = read('app/templates/access/identity_providers/partials/_tabs.html')
    shared = read('app/templates/components/framed_workspace_tabs.html')
    Environment().parse(tabs)
    Environment().parse(shared)

    assert 'framed_tabs.render_navigation(' in tabs
    assert 'data-kaori-idp-workspace-navigation' in tabs
    assert 'Identity Provider workspace' in tabs
    assert "active_tab," in tabs
    assert "url_for('identity_providers.index', tab='overview')" in tabs
    assert "url_for('identity_providers.index', tab='providers')" in tabs
    assert "current_user.has_permission('identity_providers.provision')" in tabs
    assert "url_for('identity_providers.directory_provisioning')" in tabs
    assert 'hx_target=' not in tabs  # normal links, separate Directory page
    assert 'aria-current="page"' in shared
    assert 'data-kaori-tab-variant="framed-workspace-v2-server"' in shared
