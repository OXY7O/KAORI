from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERO_TEMPLATES = [
    Path('app/templates/settings/account/partials/_hero.html'),
    Path('app/templates/settings/data_lifecycle/index.html'),
    Path('app/templates/settings/general/partials/_hero.html'),
    Path('app/templates/settings/permissions/index.html'),
    Path('app/templates/settings/roles/form.html'),
    Path('app/templates/settings/roles/index.html'),
    Path('app/templates/settings/secret_reveal/index.html'),
    Path('app/templates/users/external_identities.html'),
    Path('app/templates/users/form.html'),
    Path('app/templates/users/partials/_hero.html'),
    Path('app/templates/users/providers/form.html'),
    Path('app/templates/users/providers/index.html'),
    Path('app/templates/users/reset_password.html'),
]


def _text(path: Path) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_all_access_and_settings_heroes_use_shared_kaori_shell() -> None:
    for template in HERO_TEMPLATES:
        text = _text(template)
        assert 'page_hero.shell_classes()' in text, template
        assert 'page_hero.layout_classes()' in text, template
        assert 'page_hero.content_classes()' in text, template
        assert 'page_hero.aside_classes()' in text, template
        assert 'page_hero.context_panel_classes()' in text, template


def test_all_access_and_settings_heroes_use_shared_typography() -> None:
    for template in HERO_TEMPLATES:
        text = _text(template)
        assert 'page_hero.title_classes()' in text, template
        assert 'page_hero.description_classes()' in text, template
        assert 'page_hero.metadata_row_classes()' in text, template


def test_shared_hero_component_exposes_standard_context_primitives() -> None:
    text = _text(Path('app/templates/components/page_hero.html'))
    for macro in (
        'context_panel_classes',
        'context_panel_eyebrow_classes',
        'context_panel_title_classes',
        'context_panel_metrics_classes',
        'context_metric',
        'context_header',
        'context_note',
        'context_actions_classes',
    ):
        assert f'macro {macro}' in text


def test_hero_context_labels_use_title_case() -> None:
    forbidden = (
        'Current section boundary',
        'Deployed release',
        'Current rendered time',
        'Registry policy',
        'Configuration sequence',
        'Credential ownership',
        'Role lifecycle',
    )
    combined = '\n'.join(_text(path) for path in HERO_TEMPLATES)
    for label in forbidden:
        assert f'>{label}<' not in combined


def test_shared_hero_description_typography_is_consistent_and_not_overridden() -> None:
    component = _text(Path('app/templates/components/page_hero.html'))
    assert 'max-w-[44rem] text-[13px] font-normal leading-5' in component
    assert 'lg:text-base' not in component

    forbidden_local_typography = (
        'max-w-[44rem] text-sm font-normal leading-6 text-brand-foreground-muted',
        'max-w-[44rem] text-[13px] font-normal leading-5 text-brand-foreground-muted',
        'max-w-[44rem] text-[15px] font-normal leading-6 text-brand-foreground-muted',
        'max-w-[44rem] text-base font-normal leading-6 text-brand-foreground-muted',
    )
    for template in HERO_TEMPLATES:
        text = _text(template)
        for forbidden in forbidden_local_typography:
            assert forbidden not in text, template


def test_shared_hero_title_typography_is_slightly_larger_and_reusable() -> None:
    component = _text(Path('app/templates/components/page_hero.html'))
    assert ('text-3xl font-bold leading-10 tracking-[-0.02em] text-brand-foreground sm:text-4xl') in component

    forbidden_local_title_typography = (
        'text-[30px] font-bold leading-9 tracking-[-0.02em]',
        'text-3xl font-bold leading-10 tracking-[-0.02em]',
        'sm:text-4xl',
    )
    for template in HERO_TEMPLATES:
        text = _text(template)
        for forbidden in forbidden_local_title_typography:
            assert forbidden not in text, template
