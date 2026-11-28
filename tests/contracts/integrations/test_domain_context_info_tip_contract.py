from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_all_operational_integration_domains_define_contextual_info_tip_copy() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    assert 'components/info_tip.html' in workspace
    expected = (
        ('orchestration', 'Orchestration Authority Boundary'),
        ('observability', 'Observability Routing'),
        ('storage', 'Storage Authority Boundary'),
        ('registry', 'Registry Authority and Evidence'),
        ('secrets_management', 'Secrets Management Authority'),
        ('source_control', 'Source Control Provider and Evidence Authority'),
    )
    for domain_key, title in expected:
        assert f"domain.key == '{domain_key}'" in workspace
        assert title in workspace

    assert 'Cluster providers remain authoritative for native control-plane state and execution.' in workspace
    assert 'Metrics Source and Alert Source remain independent reusable providers.' in workspace
    assert 'Storage providers remain authoritative for native storage state.' in workspace
    assert 'Registry providers remain authoritative for repositories, artifacts, native policies' in workspace


def test_domain_info_tip_is_owned_by_registry_and_consumer_bindings_parent_header() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    parent_start = workspace.index('Registry and Consumer Bindings')
    tabs_start = workspace.index('content_tabs.render_links', parent_start)
    parent_slice = workspace[parent_start:tabs_start]

    assert 'info_tip.render(' in parent_slice
    assert "'integration-' ~ domain.key ~ '-workspace-guidance'" in parent_slice
    assert 'domain_guidance_title' in parent_slice
    assert "placement='right'" in parent_slice
    assert "variant='guide'" in parent_slice
    # Regression: a title-level section must not silently fall back to the
    # field-level circle-help trigger. Keep the shared Info Tip controller.
    assert 'components/info_tip.html' in workspace
    assert 'info_tip.render(' in parent_slice

    binding_header = workspace.split('Consumer Binding Filters', 1)[1].split(
        'Search asset-to-source contracts',
        1,
    )[0]
    assert 'info_tip.render(' not in binding_header
    assert 'binding_guidance_title' not in workspace
    assert 'binding_guidance_text' not in workspace
    assert 'binding_guidance_items' not in workspace


def test_domain_guidance_is_available_before_both_workspace_tabs() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    tip_index = workspace.index('info_tip.render(')
    tab_row = workspace.index('content_tabs.render_links', tip_index)
    registry_branch = workspace.index('{% if active_tab == "registry" %}', tab_row)

    assert tip_index < tab_row < registry_branch


def test_integrations_overview_owns_authority_guidance_without_duplicate_panels() -> None:
    overview = read('app/templates/integrations/overview.html')

    assert 'components/info_tip.html' in overview
    assert "info_tip.render('integration-portfolio-snapshot-guide'," in overview
    assert "info_tip.render('integration-domain-guidance'" not in overview
    assert 'Integration Portfolio Snapshot' in overview
    assert 'Connection and Authority Boundary' not in overview
    assert 'Coverage Boundary' not in overview
    assert "info_tip.render('integration-domain-coverage-guide'," in overview
    assert 'Register provider endpoints once and use explicit asset bindings where applicable.' in overview
    assert 'External provider systems remain authoritative for configuration, runtime state, and lifecycle decisions.' in overview


def test_shared_domain_template_has_no_duplicate_boundary_footer() -> None:
    domain = read('app/templates/integrations/domain.html')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    assert 'data-kaori-domain-operating-boundary' not in domain
    assert 'Domain Operating Boundary' not in domain
    assert 'compatibility and Core Validation' in workspace
    assert 'binding-specific consumer evidence, and consumer eligibility' in workspace
    assert "variant='guide'" in workspace
