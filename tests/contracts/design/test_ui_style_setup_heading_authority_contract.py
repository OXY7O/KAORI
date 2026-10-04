from pathlib import Path

from scripts import verify_ui_style

ROOT = Path(__file__).resolve().parents[3]
SETUP_TEMPLATE = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'setup_required.html'
INFO_FLOW_TEMPLATE = ROOT / 'app' / 'templates' / 'components' / 'info_flow.html'
INFO_FLOW_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'INFO_FLOW.md'


def test_canonical_auth_setup_heading_is_not_counted_as_custom_hero_title() -> None:
    source = (
        '<h1 data-kaori-auth-setup-heading-authority="readiness-workspace" '
        'class="mt-0.5 text-2xl font-semibold leading-8 text-content-primary">'
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
    source = '<h1 class="text-2xl font-bold">Custom setup heading</h1>'

    assert (
        verify_ui_style._count_custom_hero_titles(
            'app/templates/access/authentication/setup_required.html',
            source,
        )
        == 1
    )


def test_auth_setup_workspace_uses_compact_control_workspace_hierarchy() -> None:
    source = SETUP_TEMPLATE.read_text(encoding='utf-8')

    assert 'data-kaori-setup-workspace="release-v2"' in source
    assert 'data-kaori-setup-unified-surface' in source
    assert 'data-kaori-setup-readiness-strip' in source
    assert 'data-kaori-setup-primary-action' in source
    assert 'data-kaori-setup-supporting-grid' in source
    assert 'data-kaori-auth-setup-heading-authority="readiness-workspace"' in source
    assert 'class="mt-0.5 text-2xl font-semibold leading-8 text-content-primary"' in source
    assert 'tracking-tight' not in source
    assert 'sm:text-3xl' not in source
    assert 'max-w-4xl overflow-hidden rounded-2xl' not in source

    assert '{% import "components/action_button.html" as action_button %}' in source
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
    assert "action_button.classes('secondary')" in source
    assert 'embedded=true' in source
    assert '<ol ' not in source

    assert source.index('Development Bootstrap') < source.index('Initialization Path')
    assert source.index('Initialization Path') < source.index('Setup Details')
    assert 'Readiness Summary' not in source
    assert 'Manual Initialization Commands' in source
    assert 'Missing Schema Objects' in source
    assert 'Retry Setup Check' in source
    assert 'PostgreSQL Is Unavailable' in source


def test_info_flow_embedded_mode_preserves_shared_timeline_without_nested_card_shell() -> None:
    component = INFO_FLOW_TEMPLATE.read_text(encoding='utf-8')
    standard = INFO_FLOW_STANDARD.read_text(encoding='utf-8')

    assert 'embedded=false' in component
    assert "{% if embedded %}bg-transparent{% else %}" in component
    assert "'pb-4' if embedded else 'px-5 py-4'" in component
    assert "'pt-0' if embedded else 'border-t border-outline-default px-5 py-4'" in component
    assert 'embedded=true' in standard
    assert 'parent-owned surface' in standard
