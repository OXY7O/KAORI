"""Identity Provider source contracts reflect the approved shared Access workspace."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = 'app/templates/access/identity_providers/partials/_overview.html'
DIRECTORY = 'app/templates/access/identity_providers/partials/_directory_provisioning_strip.html'


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_overview_compacts_metrics_and_governance_in_shared_section() -> None:
    template = _read(OVERVIEW)
    Environment().parse(template)

    assert 'components/table_label.html' in template
    assert 'table_label.status_indicator_label(summary.posture_label, summary.posture_tone)' in template
    assert 'data-kaori-idp-overview-metrics' in template
    assert 'data-kaori-idp-governance-boundaries' in template
    assert 'data-kaori-idp-posture-metric' in template
    assert 'data-kaori-idp-governance-item' in template
    for field in ('configured', 'enabled', 'directory', 'sso'):
        assert f'summary.{field}' in template
    for boundary in (
        'Provider & Adapter',
        'Credential Ownership',
        'Identity Projection',
        'Authorization Boundary',
    ):
        assert boundary in template
    assert 'External secrets; KAORI stores references.' in template
    assert 'KAORI roles and account state gate access.' in template


def test_provider_directory_strip_reuses_governed_flow_without_duplicate_cards() -> None:
    template = _read(DIRECTORY)
    Environment().parse(template)

    assert 'components/table.html' in template
    assert 'data-kaori-idp-directory-flow' in template
    assert 'data-kaori-idp-directory-providers' in template
    assert 'data-kaori-idp-directory-links' in template
    assert 'data-kaori-idp-directory-authorization' in template
    assert "current_user.has_permission('identity_providers.provision')" in template
    assert '{% if not can_provision %}' in template
    assert "table_label.status_indicator_label('Read Only', 'unknown')" in template
    assert '{% if can_provision %}' in template
    assert "url_for('identity_providers.directory_provisioning')" in template
    assert 'data-kaori-idp-directory-launch' in template
    assert 'summary.directory' in template
    assert 'summary.directory_identity_links' in template
    assert 'Provider credentials remain external.' in template
    assert 'Application authorization remains local.' in template


def test_provider_hero_and_registry_remain_separate_authority() -> None:
    page = _read('app/templates/access/identity_providers/index.html')
    workspace = _read('app/templates/access/identity_providers/partials/_workspace.html')
    registry = _read('app/templates/access/identity_providers/partials/_registry.html')
    for template in (page, workspace, registry):
        Environment().parse(template)

    assert 'page_hero.context_card(' in page
    assert "current_user.has_permission('identity_providers.manage')" in page
    assert 'access/identity_providers/partials/_workspace.html' in page
    assert "active_tab == 'directory'" in workspace
    assert 'access/identity_providers/partials/_directory_provisioning_strip.html' in workspace
    assert 'access/identity_providers/partials/_registry.html' in workspace
    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.footer(' in registry
    detail = _read('app/templates/access/identity_providers/partials/_provider_detail.html')
    assert "current_user.has_permission('identity_providers.manage')" in detail
    assert "current_user.has_permission('identity_providers.provision')" in detail
    assert 'name="csrf_token"' in detail
    assert "url_for('identity_providers.edit', provider_id=provider.id)" not in registry
