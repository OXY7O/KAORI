from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app' / 'templates'
PAGE_HERO = TEMPLATES / 'components' / 'page_hero.html'


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _hero_templates() -> list[Path]:
    return sorted(
        path
        for path in TEMPLATES.rglob('*.html')
        if 'page_hero.shell_classes()' in _text(path) and '<h1' in _text(path)
    )


def test_shared_hero_component_owns_all_visual_primitives() -> None:
    source = _text(PAGE_HERO)
    required_macros = {
        'shell_classes',
        'layout_classes',
        'content_classes',
        'aside_classes',
        'title_classes',
        'description_classes',
        'metadata_row_classes',
        'context_panel_classes',
        'context_panel_eyebrow_classes',
        'context_panel_title_classes',
        'context_icon_classes',
        'context_panel_metrics_classes',
        'context_metric_card_classes',
        'context_metric_label_classes',
        'context_metric_value_classes',
        'context_metric_description_classes',
        'context_actions_classes',
        'context_action_classes',
        'context_single_action_classes',
        'primary_action_classes',
        'secondary_action_classes',
        'intro',
        'meta_label',
    }
    missing = [name for name in sorted(required_macros) if f'macro {name}(' not in source]
    assert not missing, f'Shared hero macros missing: {missing}'


def test_every_authenticated_hero_uses_the_shared_structure() -> None:
    heroes = _hero_templates()
    assert len(heroes) >= 74, f'Expected the full KAORI hero estate; found only {len(heroes)}'

    failures: list[str] = []
    for path in heroes:
        source = _text(path)
        required = {
            'layout': 'page_hero.layout_classes()',
            'content': 'page_hero.content_classes()',
            'intro': 'page_hero.intro(',
            'title': 'page_hero.title_classes()',
            'description': 'page_hero.description_classes()',
        }
        for label, token in required.items():
            if token not in source:
                failures.append(f'{path.relative_to(ROOT)}: missing shared {label}')

        if 'page_hero.metadata_row_classes()' not in source and '_hero_metadata.html' not in source:
            failures.append(f'{path.relative_to(ROOT)}: missing shared metadata row')

        has_direct_context = 'page_hero.aside_classes()' in source and 'page_hero.context_panel_classes()' in source
        has_domain_context = 'hero_context(' in source
        has_async_context = '_hero_posture' in source or '_blocked_posture' in source
        if not (has_direct_context or has_domain_context or has_async_context):
            failures.append(f'{path.relative_to(ROOT)}: missing reusable right-side context panel')

    assert not failures, '\n'.join(failures)


def test_legacy_page_local_hero_geometry_is_removed() -> None:
    forbidden = {
        'legacy shell': 'relative overflow-hidden rounded-2xl border border-brand-outline bg-kaori-primary p-5 text-brand-foreground shadow-sm lg:p-6',
        'legacy grid': 'relative grid gap-5 xl:grid-cols-12 xl:items-stretch',
        'legacy content': 'flex min-w-0 flex-col justify-center xl:col-span-7',
        'legacy title': 'text-2xl font-bold leading-tight tracking-tight text-brand-foreground lg:text-[1.75rem]',
        'legacy alternate title': 'text-2xl font-semibold leading-tight tracking-tight text-brand-foreground lg:text-[1.75rem]',
        'legacy description': 'mt-2 max-w-3xl text-sm font-medium leading-6 text-brand-foreground-muted sm:text-base',
        'legacy metadata row': 'mt-5 flex flex-wrap gap-2',
        'legacy context panel': 'min-h-[12rem] flex-col rounded-xl border border-brand-outline bg-brand-surface-strong',
    }
    failures: list[str] = []
    for path in TEMPLATES.rglob('*.html'):
        if path == PAGE_HERO:
            continue
        source = _text(path)
        for label, token in forbidden.items():
            if token in source:
                failures.append(f'{path.relative_to(ROOT)}: {label}')
    assert not failures, '\n'.join(failures)


def test_reference_integration_heroes_use_the_same_shared_contract() -> None:
    references = [
        TEMPLATES / 'integrations' / 'partials' / '_hero.html',
        TEMPLATES / 'integrations' / 'kubernetes.html',
    ]
    for path in references:
        source = _text(path)
        for token in (
            'page_hero.shell_classes()',
            'page_hero.layout_classes()',
            'page_hero.content_classes()',
            'page_hero.intro(',
            'page_hero.title_classes()',
            'page_hero.description_classes()',
            'page_hero.metadata_row_classes()',
            'page_hero.aside_classes()',
            'page_hero.context_panel_classes()',
            'page_hero.context_panel_metrics_classes()',
        ):
            assert token in source, f'{path.relative_to(ROOT)} must use {token}'


def test_no_unmanaged_authenticated_violet_h1_hero_remains() -> None:
    failures: list[str] = []
    for path in TEMPLATES.rglob('*.html'):
        relative = path.relative_to(TEMPLATES)
        if relative.parts[0] == 'auth':
            continue
        source = _text(path)
        if '<h1' not in source or 'bg-kaori-primary' not in source:
            continue
        if 'page_hero.shell_classes()' not in source and relative.parts[0] != 'components':
            failures.append(str(path.relative_to(ROOT)))
    assert not failures, 'Unmanaged authenticated Violet heroes remain:\n' + '\n'.join(failures)


def test_right_side_hero_actions_use_shared_white_context_action() -> None:
    component = _text(PAGE_HERO)
    macro_match = re.search(
        r'macro context_action_classes\(\).*?\n([\s\S]*?)\n\{%- endmacro',
        component,
    )
    assert macro_match, 'Shared context action macro is missing'
    macro_classes = macro_match.group(1)
    assert 'primary_action_classes()' in macro_classes
    assert 'w-full' in macro_classes

    primary_match = re.search(
        r'macro primary_action_classes\(\).*?\n([\s\S]*?)\n\{%- endmacro',
        component,
    )
    assert primary_match, 'Shared primary action macro is missing'
    primary_classes = primary_match.group(1)
    for token in ('bg-white', 'text-kaori-primary', 'border-white/70'):
        assert token in primary_classes, f'Context action must retain white KAORI treatment: {token}'

    failures: list[str] = []
    aside_pattern = re.compile(r'<aside\b[^>]*page_hero\.aside_classes\(\)[\s\S]*?</aside>')
    action_pattern = re.compile(r'<(?:a|button)\b[\s\S]*?>')
    class_pattern = re.compile(r'class\s*=\s*(["\'])([\s\S]*?)\1')

    for path in TEMPLATES.rglob('*.html'):
        source = _text(path)
        for aside in aside_pattern.findall(source):
            for action in action_pattern.findall(aside):
                class_match = class_pattern.search(action)
                if not class_match:
                    failures.append(f'{path.relative_to(ROOT)}: hero context action has no class')
                    continue
                classes = class_match.group(2)
                if not (
                    'page_hero.context_action_classes()' in classes
                    or 'page_hero.context_single_action_classes()' in classes
                ):
                    failures.append(f'{path.relative_to(ROOT)}: hero context action bypasses shared white style')

    assert not failures, '\n'.join(failures)
