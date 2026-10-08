from pathlib import Path

from scripts import verify_ui_style

ROOT = Path(__file__).resolve().parents[3]
SETUP_TEMPLATE = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'setup_required.html'
INFO_FLOW_TEMPLATE = ROOT / 'app' / 'templates' / 'components' / 'info_flow.html'
INFO_FLOW_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'INFO_FLOW.md'


def test_canonical_auth_setup_heading_is_not_counted_as_custom_hero_title() -> None:
    source = (
        '<h1 data-kaori-auth-setup-heading-authority="readiness-workspace" '
        'class="text-lg font-semibold leading-6 text-content-primary">'
        'Database Setup Required</h1>'
    )

    assert (
        verify_ui_style._count_custom_hero_titles(
            'app/templates/access/authentication/setup_required.html',
            source,
        )
        == 0
    )


def test_unmarked_setup_heading_remains_custom_hero_title_debt() -> None:
    source = '<h1 class="text-lg font-bold">Custom setup heading</h1>'

    assert (
        verify_ui_style._count_custom_hero_titles(
            'app/templates/access/authentication/setup_required.html',
            source,
        )
        == 1
    )


def test_auth_setup_workspace_uses_console_first_laptop_composition() -> None:
    source = SETUP_TEMPLATE.read_text(encoding='utf-8')

    assert 'data-kaori-setup-workspace="release-v4"' in source
    assert 'data-kaori-setup-readiness-strip' in source
    assert 'data-kaori-setup-console' in source
    assert 'data-kaori-setup-flow' in source
    assert 'data-kaori-auth-setup-heading-authority="readiness-workspace"' in source
    assert 'class="text-lg font-semibold leading-6 text-content-primary"' in source

    assert 'max-w-5xl' in source
    assert 'lg:grid-cols-3' in source
    assert 'lg:col-span-2' in source
    assert 'data-kaori-setup-unified-surface' not in source
    assert 'data-kaori-setup-control-grid' not in source
    assert 'lg:grid-cols-12' not in source
    assert 'text-xl font-semibold leading-7' not in source

    assert 'components/operational_flow_steps.html' in source
    assert 'components/view_more_content.html' in source
    assert 'components/section_link_button.html' in source
    assert 'components/table_label.html' in source
    assert 'components/terminal_command.html' in source
    assert 'components/operational_callout.html' in source
    assert 'components/info_flow.html' not in source
    assert 'components/operational_section_card.html' not in source

    assert "table_label.status_indicator_label('Reachable', 'normal')" in source
    assert "table_label.status_indicator_label('Missing', 'warning')" in source
    assert "table_label.status_indicator_label('Blocked', 'critical')" in source
    assert "section_link_button.render(url_for('auth.login') , 'Retry Setup Check', icon='refresh-cw')" in source
    assert 'compact=true' in source
    assert 'operational_flow_steps.render(initialization_flow_rows' in source
    assert 'view_more_content.render(' in source

    assert source.index('Development Bootstrap') < source.index('Initialization Path')
    assert source.index('Initialization Path') < source.index('Advanced Setup')
    assert 'Readiness Summary' not in source
    assert 'Manual Initialization Commands' in source
    assert 'Missing Schema Objects' in source
    assert 'PostgreSQL Is Unavailable' in source


def test_info_flow_embedded_mode_remains_a_shared_component_option() -> None:
    component = INFO_FLOW_TEMPLATE.read_text(encoding='utf-8')
    standard = INFO_FLOW_STANDARD.read_text(encoding='utf-8')

    assert 'embedded=false' in component
    assert '{% if embedded %}bg-transparent{% else %}' in component
    assert "'pb-3' if embedded else 'px-5 py-4'" in component
    assert "'h-8 w-8 rounded-lg' if embedded else 'h-11 w-11 rounded-xl'" in component
    assert "'h-4 w-4' if embedded else 'h-5 w-5'" in component
    assert "'text-xs leading-5 text-content-muted' if embedded" in component
    assert "'space-y-3' if embedded else 'space-y-4'" in component
    assert "'pt-0' if embedded else 'border-t border-outline-default px-5 py-4'" in component

    assert 'Embedded mode is intentionally denser than the standalone card' in standard
    assert '32 px icon surface with a 16 px icon' in standard
    assert '12 px supporting description' in standard
    assert 'parent-owned operational surfaces' in standard
