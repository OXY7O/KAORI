from scripts import verify_ui_style


def test_canonical_auth_setup_heading_is_not_counted_as_custom_hero_title() -> None:
    source = (
        '<h1 data-kaori-auth-setup-heading-authority="readiness-workspace" '
        'class="mt-1 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">'
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
