from pathlib import Path

from scripts import verify_ui_style

ROOT = Path(__file__).resolve().parents[3]
SETUP_TEMPLATE = ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'setup_required.html'


def test_canonical_auth_setup_heading_is_not_counted_as_custom_hero_title() -> None:
    source = (
        '<h1 data-kaori-auth-setup-heading-authority="readiness-workspace" '
        'class="mt-1 text-xl font-semibold leading-7 tracking-tight text-content-primary sm:text-2xl sm:leading-8">'
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


def test_auth_setup_header_uses_compact_readiness_workspace_hierarchy() -> None:
    source = SETUP_TEMPLATE.read_text(encoding='utf-8')

    assert 'px-5 py-4 sm:px-7 sm:py-5 lg:px-8' in source
    assert 'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between' in source
    assert 'flex min-w-0 items-start gap-3' in source
    assert 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl' in source
    assert (
        'class="mt-1 text-xl font-semibold leading-7 tracking-tight '
        'text-content-primary sm:text-2xl sm:leading-8"'
    ) in source
    assert 'mt-1.5 max-w-2xl text-sm leading-6 text-content-secondary' in source
    assert 'sm:text-3xl' not in source
    assert 'text-2xl font-bold tracking-tight text-content-primary sm:text-3xl' not in source
    assert 'PostgreSQL Reachable' in source
    assert 'Schema Missing' in source
