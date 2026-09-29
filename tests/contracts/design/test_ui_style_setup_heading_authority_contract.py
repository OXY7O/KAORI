from pathlib import Path

from scripts import verify_ui_style

ROOT = Path(__file__).resolve().parents[3]
SETUP_TEMPLATE = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'setup_required.html'


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


def test_auth_setup_workspace_uses_canonical_operational_hierarchy() -> None:
    source = SETUP_TEMPLATE.read_text(encoding='utf-8')

    assert 'data-kaori-setup-workspace="release-v2"' in source
    assert 'data-kaori-auth-setup-heading-authority="readiness-workspace"' in source
    assert 'class="mt-0.5 text-2xl font-semibold leading-8 text-content-primary"' in source
    assert 'tracking-tight' not in source
    assert 'sm:text-3xl' not in source
    assert 'max-w-4xl overflow-hidden rounded-2xl' not in source

    assert '{% import "components/table_label.html" as table_label %}' in source
    assert '{% import "components/info_flow.html" as info_flow %}' in source
    assert '{% import "components/operational_section_card.html" as operational_section_card %}' in source
    assert 'table_label.status_indicator_label("PostgreSQL Reachable", "normal")' in source
    assert 'table_label.status_indicator_label("Schema Missing", "warning")' in source
    assert 'operational_section_card.render(' in source
    assert 'info_flow.render(' in source
    assert '<ol ' not in source

    assert source.index('Development Bootstrap') < source.index('Initialization Path')
    assert 'PostgreSQL Reachable' in source
    assert 'Schema Missing' in source
