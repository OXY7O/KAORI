from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERO = ROOT / 'app' / 'templates' / 'components' / 'page_hero.html'
STANDARD = ROOT / 'docs' / 'design' / 'components' / 'HERO.md'
DARK_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'DARK_MODE.md'
ANALYTICS_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'ANALYTICS_HERO.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'

REMOVED_MACROS = (
    'context_posture_header',
    'context_posture_note',
    'context_bottom_notice',
    'action_group_classes',
    'secondary_action_classes',
    'destructive_action_classes',
    'supporting_strip',
)

REMOVED_DOCUMENTS = (
    ROOT / 'docs' / 'design' / 'components' / 'ANALYTICS_HERO_STANDARD.md',
    ROOT / 'docs' / 'design' / 'components' / 'ANALYTICS_HERO_INVENTORY_REFERENCE.md',
)

REMOVED_TESTS = (
    ROOT / 'tests' / 'contracts' / 'analytics' / 'test_analytics_hero_posture_note_standard_contract.py',
    ROOT / 'tests' / 'contracts' / 'analytics' / 'test_inventory_aligned_analytics_hero_contract.py',
)

REQUIRED_MACROS = (
    'shell_classes',
    'layout_classes',
    'content_classes',
    'aside_classes',
    'context_panel_classes',
    'context_status_badge',
    'context_card_body',
    'context_card',
    'context_panel_eyebrow_classes',
    'context_panel_title_classes',
    'context_icon_classes',
    'context_icon_box',
    'context_action_icon_box',
    'context_metric_card_classes',
    'context_metric_label_classes',
    'context_metric_value_classes',
    'context_metric_helper_classes',
    'context_action_classes',
    'context_single_action_classes',
    'context_header',
    'context_header_action',
    'context_header_status',
    'context_actions_classes',
    'context_info',
    'context_panel_metrics_classes',
    'context_metric',
    'title_classes',
    'description_classes',
    'metadata_row_classes',
    'intro',
    'meta_label',
)

IMPLEMENTATION_TOKENS = (
    'min-h-[15.5rem]',
    'lg:min-h-[17.5rem]',
    'rounded-2xl',
    'p-5',
    'lg:p-6',
    'min-h-[13rem]',
    'lg:min-h-[14.5rem]',
    'flex h-full min-h-[13rem] flex-col gap-3',
    'xl:grid-cols-12',
    'xl:col-span-7',
    'xl:col-span-5',
    'kaori-hero-shell',
    'kaori-hero-panel',
    'kaori-hero-tile',
    'kaori-hero-chip',
    'metrics[:2]',
    'text-3xl font-bold leading-10',
    'sm:text-4xl',
    'max-w-[44rem] text-base font-normal leading-7',
    'min-h-8 items-center gap-2 rounded-md',
    'text-lg font-semibold leading-6',
    'text-xs font-semibold leading-5',
    'grid grid-cols-2 auto-rows-fr gap-2',
    'mt-auto flex min-h-10 items-center gap-2',
    'mt-auto grid min-h-10 gap-2',
    'h-10 cursor-pointer',
    'macro context_icon_box(icon)',
    'macro context_action_icon_box(icon, href, aria_label, title=None)',
    'macro context_header_action(eyebrow_label, title, icon, href, aria_label)',
    "macro context_header_status(eyebrow_label, title, status_label, status_tone='info')",
    'macro context_metric_value_classes()',
    'macro context_single_action_classes()',
)

DOCUMENTATION_TOKENS = (
    '# KAORI Hero Component Standard v1.5',
    'app/templates/components/page_hero.html',
    'scripts/verify_hero_component_standard.py',
    'tests/contracts/design/test_hero_component_standard_contract.py',
    '248 px / 280 px minimum',
    'same 12 px row rhythm',
    '16 px, regular, 28 px line height',
    'Action Icon Box',
    'Context Icon Box',
    'Status Badge Box',
    'Do not invent a fourth header-accessory geometry.',
    'exactly two compact metrics',
    'metrics[:2]',
    'components/ANALYTICS_HERO.md',
    '## Theme and surface contract',
    'components/DARK_MODE.md',
    '## Change procedure',
)

STALE_DOC_REFERENCES = (
    'tests/contracts/ui/test_global_hero_reusability_contract.py',
    'tests/ui/test_hero_context_panel_contract.py',
    'ANALYTICS_HERO_STANDARD.md',
    'ANALYTICS_HERO_INVENTORY_REFERENCE.md',
    '13 px hero description',
    'renders at 13 px',
)


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f'Missing required Hero standard file: {path.relative_to(ROOT)}')
    return path.read_text(encoding='utf-8')


def _require_tokens(source: str, tokens: tuple[str, ...], owner: str) -> None:
    missing = [token for token in tokens if token not in source]
    if missing:
        raise AssertionError(f'{owner}: missing canonical tokens: {", ".join(missing)}')


def _macro_names(source: str) -> set[str]:
    return set(re.findall(r'{%\s*macro\s+([A-Za-z0-9_]+)', source))


def _hero_shell_templates() -> list[Path]:
    templates: list[Path] = []
    for path in (ROOT / 'app' / 'templates').rglob('*.html'):
        source = path.read_text(encoding='utf-8')
        if 'page_hero.shell_classes()' in source:
            templates.append(path)
    return sorted(templates)


def _verify_shell_template(path: Path) -> None:
    source = path.read_text(encoding='utf-8')
    relative = path.relative_to(ROOT)

    required = (
        'import "components/page_hero.html" as page_hero',
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        'page_hero.intro(',
        'page_hero.title_classes()',
        'page_hero.description_classes()',
    )
    _require_tokens(source, required, str(relative))

    for match in re.finditer(r'<h1\s+class=\"([^\"]+)\"', source):
        if 'page_hero.title_classes()' not in match.group(1):
            raise AssertionError(f'{relative}: Hero h1 bypasses page_hero.title_classes()')

    if 'text-[13px]' in source or 'text-[15px]' in source:
        raise AssertionError(f'{relative}: page-local arbitrary Hero typography is prohibited')

    for macro in REMOVED_MACROS:
        if f'page_hero.{macro}(' in source:
            raise AssertionError(f'{relative}: references removed Hero macro {macro}()')


def verify() -> None:
    hero = _read(HERO)
    standard = _read(STANDARD)
    analytics_standard = _read(ANALYTICS_STANDARD)
    dark_standard = _read(DARK_STANDARD)

    _require_tokens(hero, IMPLEMENTATION_TOKENS, 'page_hero implementation')

    macros = _macro_names(hero)
    missing_macros = sorted(set(REQUIRED_MACROS) - macros)
    if missing_macros:
        raise AssertionError(f'page_hero implementation: missing required macros: {", ".join(missing_macros)}')

    present_removed = sorted(set(REMOVED_MACROS) & macros)
    if present_removed:
        raise AssertionError(f'page_hero implementation: removed macros still exist: {", ".join(present_removed)}')

    for path in REMOVED_DOCUMENTS:
        if path.exists():
            raise AssertionError(f'Obsolete duplicate Hero document still exists: {path.relative_to(ROOT)}')

    for path in REMOVED_TESTS:
        if path.exists():
            raise AssertionError(f'Obsolete duplicate Hero test still exists: {path.relative_to(ROOT)}')

    _require_tokens(standard, DOCUMENTATION_TOKENS, 'Hero standard documentation')
    _require_tokens(
        dark_standard,
        ('# KAORI Dark Mode Standard v1.0', 'kaori-hero-shell', 'canonical dark Hero gradient'),
        'Dark-mode Hero contract',
    )
    _require_tokens(
        analytics_standard,
        (
            '# Kubernetes Analytics Hero Extension',
            'page_hero.context_card(...)',
            'page_hero.context_card_body(...)',
            'exactly two posture metrics',
            'one full-width `Manage Clusters` action',
        ),
        'Analytics Hero extension',
    )

    documentation = '\n'.join(path.read_text(encoding='utf-8') for path in (ROOT / 'docs').rglob('*.md'))
    stale = [token for token in STALE_DOC_REFERENCES if token in documentation]
    if stale:
        raise AssertionError(f'Documentation still contains stale Hero references: {", ".join(stale)}')

    shell_templates = _hero_shell_templates()
    if not shell_templates:
        raise AssertionError('No authenticated Hero shell templates were discovered')
    for path in shell_templates:
        _verify_shell_template(path)

    active_templates = '\n'.join(
        path.read_text(encoding='utf-8') for path in (ROOT / 'app' / 'templates').rglob('*.html') if path != HERO
    )
    for macro in REMOVED_MACROS:
        if f'page_hero.{macro}(' in active_templates:
            raise AssertionError(f'Active templates still reference removed Hero macro {macro}()')

    quality_gate = _read(QUALITY_GATE)
    if 'python scripts/verify_hero_component_standard.py' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not execute the Hero standard verifier')

    context_card_templates = sum(
        1
        for path in (ROOT / 'app' / 'templates').rglob('*.html')
        if 'page_hero.context_card(' in path.read_text(encoding='utf-8')
    )
    lazy_context_templates = sum(
        1
        for path in (ROOT / 'app' / 'templates').rglob('*.html')
        if 'page_hero.context_card_body(' in path.read_text(encoding='utf-8')
    )

    print(
        'KAORI Hero component standard passed: '
        f'{len(shell_templates)} Hero shells, {context_card_templates} context-card consumers, '
        f'and {lazy_context_templates} lazy context bodies match v1.5; implementation, documentation, '
        'domain extension, dark-mode ownership, removed APIs, and quality-gate ownership are synchronized.'
    )


if __name__ == '__main__':
    verify()
