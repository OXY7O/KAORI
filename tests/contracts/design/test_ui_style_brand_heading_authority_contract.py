from scripts import verify_ui_style


def test_canonical_auth_brand_heading_is_not_counted_as_custom_hero_title() -> None:
    source = (
        '<h1 data-kaori-auth-brand-heading-authority="intentional-brand-lockup" '
        'class="text-2xl font-bold">Operate with Clarity.</h1>'
    )

    assert (
        verify_ui_style._count_custom_hero_titles(
            'app/templates/access/authentication/partials/_brand_panel.html',
            source,
        )
        == 0
    )


def test_unmarked_page_heading_remains_custom_hero_title_debt() -> None:
    source = '<h1 class="text-2xl font-bold">Custom page heading</h1>'

    assert verify_ui_style._count_custom_hero_titles('app/templates/example.html', source) == 1
