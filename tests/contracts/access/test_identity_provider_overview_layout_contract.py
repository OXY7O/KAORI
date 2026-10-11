"""Identity Providers Overview follows the shared compact Access workspace composition."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = "app/templates/access/identity_providers/partials/_overview.html"
DIRECTORY = "app/templates/access/identity_providers/partials/_directory_provisioning_strip.html"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_provider_overview_compacts_metrics_and_governance_in_shared_section() -> None:
    template = _read(OVERVIEW)
    Environment().parse(template)

    assert 'components/operational_section_card.html' in template
    assert 'components/table_label.html' in template
    assert "operational_section.render(" in template
    assert 'header_badge=table_label.status_indicator_label(summary.posture_label, summary.posture_tone)' in template
    assert 'data-kaori-idp-overview-metrics' in template
    assert 'grid-cols-2 gap-3 p-4 sm:p-5 xl:grid-cols-4' in template
    for field in ('configured', 'enabled', 'directory', 'sso'):
        assert f'summary.{field}' in template
    for title in (
        'Provider / Adapter Boundary',
        'Credential Ownership',
        'Identity Projection',
        'Authorization Boundary',
    ):
        assert title in template
    assert 'data-kaori-idp-governance-boundaries' in template
    assert 'md:grid-cols-2' in template
    assert 'Configured does not mean connection-tested.' in template
    assert 'grid gap-px bg-outline-subtle' not in template
    assert "rounded-xl border border-outline-default bg-surface-card p-5 shadow-sm" not in template
    assert template.count('{% call ') == template.count('{% endcall %}')
    assert 'access/identity_providers/partials/_directory_provisioning_strip.html' in template


def test_provider_directory_strip_reuses_governed_flow_without_duplicate_cards() -> None:
    template = _read(DIRECTORY)
    Environment().parse(template)

    assert 'components/operational_section_card.html' in template
    assert 'components/operational_point_flow.html' in template
    assert "operational_section.render(" in template
    assert "point_flow.render(directory_flow," in template
    assert 'data-kaori-idp-directory-flow' in template
    assert "current_user.has_permission('identity_providers.provision')" in template
    assert "action_href=url_for('identity_providers.directory_provisioning') if can_provision else none" in template
    assert "header_badge=table_label.status_indicator_label('Read Only', 'unknown') if not can_provision else none" in template
    assert 'summary.directory' in template
    assert 'summary.directory_identity_links' in template
    assert 'Directory Sources' in template
    assert 'Identity Projection' in template
    assert 'Local Authorization' in template
    assert 'directory credentials remain external' in template
    assert 'sm:divide-x' not in template
    assert template.count('{% call ') == template.count('{% endcall %}')


def test_provider_hero_and_registry_remain_separate_authority() -> None:
    page = _read('app/templates/access/identity_providers/index.html')
    registry = _read('app/templates/access/identity_providers/partials/_registry.html')
    assert 'page_hero.context_card(' in page
    assert "current_user.has_permission('identity_providers.manage')" in page
    assert "active_tab == 'providers'" in page
    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.footer(' in registry
