from pathlib import Path

from scripts import verify_ui_style

ROOT = Path(__file__).resolve().parents[3]
SETUP_TEMPLATE = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'setup_required.html'
INFO_FLOW_TEMPLATE = ROOT / 'app' / 'templates' / 'components' / 'info_flow.html'
INFO_FLOW_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'INFO_FLOW.md'


def test_canonical_auth_setup_heading_is_not_counted_as_custom_hero_title() -> None:
    source = (
        '<h1 data-kaori-auth-setup-heading-authority="readiness-workspace" '
        'class="text-xl font-semibold leading-7 text-content-primary">'
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
    source = '<h1 class="text-xl font-bold">Custom setup heading</h1>'

    assert (
        verify_ui_style._count_custom_hero_titles(
            'app/templates/access/authentication/setup_required.html',
            source,
        )
        == 1
    )


def test_auth_setup_workspace_uses_compact_laptop_control_grid() -> None:
    source = SETUP_TEMPLATE.read_text(encoding='utf-8')

    assert 'data-kaori-setup-workspace="release-v3"' in source
    assert 'data-kaori-setup-unified-surface' in source
    assert 'data-kaori-setup-readiness-strip' in source
    assert 'data-kaori-setup-control-grid' in source
    assert 'data-kaori-auth-setup-heading-authority="readiness-workspace"' in source
    assert 'class="text-xl font-semibold leading-7 text-content-primary"' in source

    assert 'max-w-5xl' in source
    assert 'lg:grid-cols-12' in source
    assert 'lg:col-span-8' in source
    assert 'lg:col-span-4' in source
    assert 'data-kaori-setup-primary-action' not in source
    assert 'data-kaori-setup-supporting-grid' not in source
    assert 'lg:grid-cols-[minmax(' not in source
    assert 'sm:text-3xl' not in source
    assert 'text-2xl font-semibold leading-8' not in source

    assert '{% import "components/section_link_button.html" as section_link_button %}' in source
    assert '{% import "components/table_label.html" as table_label %}' in source
    assert '{% import "components/info_flow.html" as info_flow %}' in source
    assert '{% import "components/operational_section_card.html" as operational_section_card %}' in source
    assert 'operational_section_card.shell_classes()' in source
    assert source.count('operational_section_card.shell_classes()') == 1
    assert 'operational_section_card.render(' not in source

    assert "table_label.status_label('Initialization Required', 'warning', icon='database-zap')" in source
    assert "table_label.status_indicator_label('Reachable', 'normal')" in source
    assert "table_label.status_indicator_label('Missing', 'warning')" in source
    assert "table_label.status_indicator_label('Blocked', 'critical')" in source
    assert "section_link_button.render(url_for('auth.login'), 'Retry Setup Check', icon='refresh-cw')" in source
    assert 'embedded=true' in source
    assert '<ol ' not in source

    assert source.index('Development Bootstrap') < source.index('Initialization Path')
    assert source.index('Security Boundary') < source.index('Setup Details')
    assert 'Readiness Summary' not in source
    assert 'Required Action' not in source
    assert 'Recovery Action' not in source
    assert 'Manual Initialization Commands' in source
    assert 'Missing Schema Objects' in source
    assert 'PostgreSQL Is Unavailable' in source


def test_info_flow_embedded_mode_is_compact_without_copying_timeline() -> None:
    component = INFO_FLOW_TEMPLATE.read_text(encoding='utf-8')
    standard = INFO_FLOW_STANDARD.read_text(encoding='utf-8')

    assert 'embedded=false' in component
    assert "{% if embedded %}bg-transparent{% else %}" in component
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
