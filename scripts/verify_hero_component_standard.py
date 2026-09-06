from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
HERO = TEMPLATES / 'components' / 'page_hero.html'
STANDARD = ROOT / 'docs' / 'design' / 'components' / 'HERO.md'
DARK_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'DARK_MODE.md'
ANALYTICS_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'ANALYTICS_HERO.md'
DASHBOARD_STANDARD = ROOT / 'docs' / 'design' / 'patterns' / 'OPERATIONAL_DASHBOARD.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'
INTEGRATION_TAXONOMY = ROOT / 'app' / 'definitions' / 'catalogs' / 'integrations' / 'taxonomy.yaml'

DESCRIPTION_TARGET_MIN = 7
DESCRIPTION_TARGET_MAX = 12
DESCRIPTION_HARD_MAX = 16
DESCRIPTION_WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
DESCRIPTION_PARAGRAPH_PATTERN = re.compile(
    r'<p\b(?=[^>]*page_hero\.description_classes\(\))[^>]*>(?P<body>.*?)</p>',
    flags=re.IGNORECASE | re.DOTALL,
)
OPERATIONAL_DASHBOARD_DESCRIPTION_PATTERN = re.compile(
    r"page_hero\.operational_dashboard\(\s*'[^']*',\s*'[^']*',\s*'[^']*',\s*'(?P<description>[^']*)'",
    flags=re.DOTALL,
)

KUBERNETES_ANALYTICS_HEROES = (
    TEMPLATES / 'kubernetes' / 'analytics' / 'overview' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'utilization' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'capacity' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'storage' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'workload' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'top_consumers' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'alerts' / 'partials' / '_hero.html',
    TEMPLATES / 'kubernetes' / 'analytics' / 'forecast' / 'partials' / '_hero.html',
)
OBJECT_STORAGE_ANALYTICS_HERO = TEMPLATES / 'storage' / 'object_storage' / 'analytics' / 'partials' / '_hero.html'

REMOVED_MACROS = (
    'context_posture_header',
    'context_posture_note',
    'context_bottom_notice',
    'action_group_classes',
    'secondary_action_classes',
    'destructive_action_classes',
    'supporting_strip',
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
    'blocked_context_body',
    'operational_dashboard',
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
    'analytics_metadata',
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
    'metadata[:3]',
    'data-kaori-hero-profile="operational-dashboard"',
    'data-kaori-hero-state="{{ state }}"',
    'data-kaori-analytics-metadata',
    'text-3xl font-bold leading-10',
    'sm:text-4xl',
    'max-w-[44rem] text-base font-normal leading-7',
    'grid grid-cols-2 auto-rows-fr gap-2',
    'macro blocked_context_body(',
    'macro operational_dashboard(',
    'macro analytics_metadata(',
    'macro context_icon_box(icon)',
    'macro context_action_icon_box(icon, href, aria_label, title=None)',
    "macro context_header_status(eyebrow_label, title, status_label, status_tone='info')",
)

DOCUMENTATION_TOKENS = (
    '# KAORI Hero Component Standard v1.6',
    'Hero Profile',
    'Hero State',
    'same Profile + same State',
    'exactly three metadata',
    'app/templates/components/page_hero.html',
    'scripts/verify_hero_component_standard.py',
    'tests/contracts/design/test_hero_component_standard_contract.py',
    '248 px / 280 px minimum',
    '16 px, regular, 28 px line height',
    'Action Icon Box',
    'Context Icon Box',
    'Status Badge Box',
    'Do not invent a fourth header-accessory geometry.',
    'exactly two compact metrics',
    'Blocked readiness grammar',
    'Operational workspace blocked context',
    'Missing Evidence',
    'blocked_context_body(...)',
    'components/ANALYTICS_HERO.md',
    '## Theme and surface contract',
    'components/DARK_MODE.md',
    'The canonical verifier enforces the 7–12 word target',
    'Integration domain descriptions are audited from',
    '## Change procedure',
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


def _description_words(text: str) -> list[str]:
    return DESCRIPTION_WORD_PATTERN.findall(text)


def _validate_description_budget(text: str, *, owner: str) -> None:
    word_count = len(_description_words(text))
    if word_count > DESCRIPTION_HARD_MAX:
        raise AssertionError(
            f'{owner}: Hero description has {word_count} words; hard maximum {DESCRIPTION_HARD_MAX} words'
        )
    if not DESCRIPTION_TARGET_MIN <= word_count <= DESCRIPTION_TARGET_MAX:
        raise AssertionError(
            f'{owner}: Hero description has {word_count} words; expected '
            f'{DESCRIPTION_TARGET_MIN}-{DESCRIPTION_TARGET_MAX} words'
        )


def _clean_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _integration_domain_hero_descriptions() -> dict[str, str]:
    taxonomy = _read(INTEGRATION_TAXONOMY)
    domains_section = taxonomy.split('\ncapabilities:', 1)[0]
    entries = re.finditer(
        r'(?ms)^- key: [^\n]+\n\s+label: (?P<label>[^\n]+)\n\s+description: (?P<description>[^\n]+)',
        domains_section,
    )
    descriptions = {
        _clean_yaml_scalar(match.group('label')): _clean_yaml_scalar(match.group('description')) for match in entries
    }
    if not descriptions:
        raise AssertionError('Integration taxonomy: no domain Hero descriptions were discovered')
    return descriptions


def _literal_hero_descriptions(paths: list[Path]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for path in paths:
        source = _read(path)
        match = DESCRIPTION_PARAGRAPH_PATTERN.search(source)
        if not match:
            continue
        body = match.group('body')
        if '{{' in body or '{%' in body:
            continue
        text = re.sub(r'<[^>]+>', ' ', body)
        text = html.unescape(' '.join(text.split()))
        if text:
            descriptions[str(path.relative_to(ROOT))] = text
    return descriptions


def _operational_dashboard_hero_descriptions(paths: list[Path]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for path in paths:
        source = _read(path)
        match = OPERATIONAL_DASHBOARD_DESCRIPTION_PATTERN.search(source)
        if not match:
            raise AssertionError(
                f'{path.relative_to(ROOT)}: operational-dashboard description must be a statically auditable literal'
            )
        descriptions[str(path.relative_to(ROOT))] = match.group('description')
    return descriptions


def _verify_description_budgets(primitive_shells: list[Path], profile_templates: list[Path]) -> int:
    descriptions = _literal_hero_descriptions(primitive_shells)
    descriptions.update(_operational_dashboard_hero_descriptions(profile_templates))
    descriptions.update(
        {
            f'Integration domain {label}': description
            for label, description in _integration_domain_hero_descriptions().items()
        }
    )

    failures: list[str] = []
    for owner, description in descriptions.items():
        try:
            _validate_description_budget(description, owner=owner)
        except AssertionError as exc:
            failures.append(str(exc))
    if failures:
        raise AssertionError('Hero description budget violations:\n- ' + '\n- '.join(failures))
    return len(descriptions)


def _has_unmanaged_hero_shell(source: str) -> bool:
    for opening in re.finditer(r'<(?P<tag>section|header)\b(?P<attrs>[^>]*)>', source, flags=re.IGNORECASE | re.DOTALL):
        attrs = opening.group('attrs')
        has_hero_surface = re.search(
            r'class\s*=\s*["\'][^"\']*(?:bg-kaori-primary|kaori-hero-shell)[^"\']*["\']',
            attrs,
            flags=re.DOTALL,
        )
        if not has_hero_surface:
            continue

        tag = opening.group('tag')
        remainder = source[opening.end() :]
        closing = re.search(rf'</{tag}\s*>', remainder, flags=re.IGNORECASE)
        if closing and re.search(r'<h1\b', remainder[: closing.start()], flags=re.IGNORECASE):
            return True
    return False


def _primitive_shell_templates() -> list[Path]:
    return sorted(
        path
        for path in TEMPLATES.rglob('*.html')
        if path != HERO and 'page_hero.shell_classes()' in path.read_text(encoding='utf-8')
    )


def _profile_templates() -> list[Path]:
    return sorted(
        path
        for path in TEMPLATES.rglob('*.html')
        if path != HERO and 'page_hero.operational_dashboard(' in path.read_text(encoding='utf-8')
    )


def _verify_primitive_shell(path: Path) -> None:
    source = path.read_text(encoding='utf-8')
    relative = path.relative_to(ROOT)
    _require_tokens(
        source,
        (
            'import "components/page_hero.html" as page_hero',
            'page_hero.shell_classes()',
            'page_hero.layout_classes()',
            'page_hero.content_classes()',
            'page_hero.intro(',
            'page_hero.title_classes()',
            'page_hero.description_classes()',
        ),
        str(relative),
    )
    if 'text-[13px]' in source or 'text-[15px]' in source:
        raise AssertionError(f'{relative}: page-local arbitrary Hero typography is prohibited')
    for macro in REMOVED_MACROS:
        if f'page_hero.{macro}(' in source:
            raise AssertionError(f'{relative}: references removed Hero macro {macro}()')


def _verify_operational_dashboard_profile() -> None:
    kubernetes = _read(TEMPLATES / 'kubernetes' / 'dashboard' / 'partials' / '_hero.html')
    object_storage = _read(TEMPLATES / 'storage' / 'object_storage' / 'dashboard' / 'partials' / '_hero.html')
    for name, source in (
        ('Kubernetes dashboard', kubernetes),
        ('Object Storage dashboard', object_storage),
    ):
        _require_tokens(
            source,
            ('page_hero.operational_dashboard(', "'Committed Snapshots'"),
            name,
        )
        for local_primitive in (
            'page_hero.shell_classes()',
            'page_hero.layout_classes()',
            'page_hero.content_classes()',
            'page_hero.context_panel_classes()',
        ):
            if local_primitive in source:
                raise AssertionError(f'{name}: dashboard profile must not assemble {local_primitive} locally')


def _verify_blocked_context_ownership() -> None:
    wrappers = (
        TEMPLATES / 'components' / 'cluster' / '_hero_blocked_context.html',
        TEMPLATES / 'storage' / 'object_storage' / 'inventory' / 'components' / '_hero_blocked_context.html',
        TEMPLATES / 'kubernetes' / 'analytics' / 'components' / '_blocked_posture.html',
        TEMPLATES / 'storage' / 'object_storage' / 'analytics' / 'partials' / '_hero_blocked_posture.html',
    )
    for path in wrappers:
        source = _read(path)
        relative = path.relative_to(ROOT)
        if 'page_hero.blocked_context_body(' not in source:
            raise AssertionError(f'{relative}: blocked Hero context must use blocked_context_body()')
        if 'page_hero.context_panel_classes()' in source:
            raise AssertionError(f'{relative}: blocked Hero wrapper must not assemble context panel geometry locally')


def _verify_analytics_metadata_ownership() -> None:
    for path in (*KUBERNETES_ANALYTICS_HEROES, OBJECT_STORAGE_ANALYTICS_HERO):
        source = _read(path)
        relative = path.relative_to(ROOT)
        if 'page_hero.analytics_metadata(' not in source:
            raise AssertionError(f'{relative}: Analytics Hero metadata must use analytics_metadata()')
        if 'page_hero.metadata_row_classes()' in source:
            raise AssertionError(f'{relative}: Analytics Hero must not assemble metadata-row geometry locally')

    object_storage = _read(OBJECT_STORAGE_ANALYTICS_HERO)
    if not re.search(r"evidence_label\s*=\s*['\"]Committed Snapshot Boundary['\"]", object_storage):
        raise AssertionError('Object Storage Analytics Hero: evidence label must be Committed Snapshot Boundary')
    if '{% if inventory_observed_at %}' in object_storage:
        raise AssertionError('Object Storage Analytics: metadata must not depend on inventory_observed_at')


def verify() -> None:
    hero = _read(HERO)
    standard = _read(STANDARD)
    analytics_standard = _read(ANALYTICS_STANDARD)
    dashboard_standard = _read(DASHBOARD_STANDARD)
    dark_standard = _read(DARK_STANDARD)

    _require_tokens(hero, IMPLEMENTATION_TOKENS, 'page_hero implementation')
    macros = _macro_names(hero)
    missing_macros = sorted(set(REQUIRED_MACROS) - macros)
    if missing_macros:
        raise AssertionError('page_hero implementation: missing required macros: ' + ', '.join(missing_macros))
    present_removed = sorted(set(REMOVED_MACROS) & macros)
    if present_removed:
        raise AssertionError('page_hero implementation: removed macros still exist: ' + ', '.join(present_removed))

    _require_tokens(standard, DOCUMENTATION_TOKENS, 'Hero standard documentation')
    _require_tokens(
        dark_standard,
        (
            '# KAORI Dark Mode Standard v1.0',
            'kaori-hero-shell',
            'canonical dark Hero gradient',
        ),
        'Dark-mode Hero contract',
    )
    _require_tokens(
        analytics_standard,
        (
            '# Kubernetes Analytics Hero Extension',
            'exactly two posture metrics',
            'one full-width `Manage Clusters` action',
            'Analytics Readiness',
            'Missing Evidence',
            'Blocked Analytics metadata remains exactly three items',
            'page_hero.analytics_metadata(...)',
        ),
        'Analytics Hero extension',
    )
    _require_tokens(
        dashboard_standard,
        (
            'KAORI Operational Dashboard Pattern',
            'Operational Dashboard Hero Profile',
            'Dashboard Readiness',
            'Active Scope',
            'Data Authority',
            'Object Storage Setup Required',
        ),
        'Operational Dashboard pattern',
    )

    primitive_shells = _primitive_shell_templates()
    if not primitive_shells:
        raise AssertionError('No compatibility Hero shell templates were discovered')
    for path in primitive_shells:
        _verify_primitive_shell(path)

    _verify_operational_dashboard_profile()
    _verify_blocked_context_ownership()
    _verify_analytics_metadata_ownership()

    active_templates = '\n'.join(path.read_text(encoding='utf-8') for path in TEMPLATES.rglob('*.html') if path != HERO)
    for macro in REMOVED_MACROS:
        if f'page_hero.{macro}(' in active_templates:
            raise AssertionError(f'Active templates still reference removed Hero macro {macro}()')

    suspicious_local_shells = []
    for path in TEMPLATES.rglob('*.html'):
        if path == HERO:
            continue
        source = path.read_text(encoding='utf-8')
        if _has_unmanaged_hero_shell(source):
            suspicious_local_shells.append(str(path.relative_to(ROOT)))
    if suspicious_local_shells:
        raise AssertionError('Unmanaged Hero-like shell detected: ' + ', '.join(suspicious_local_shells))

    quality_gate = _read(QUALITY_GATE)
    if 'python scripts/verify_hero_component_standard.py' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not execute the Hero standard verifier')

    profile_templates = _profile_templates()
    if len(profile_templates) != 2:
        raise AssertionError(
            f'Operational Dashboard profile must have exactly two paired references, found {len(profile_templates)}'
        )

    audited_descriptions = _verify_description_budgets(primitive_shells, profile_templates)

    context_card_templates = sum(
        1 for path in TEMPLATES.rglob('*.html') if 'page_hero.context_card(' in path.read_text(encoding='utf-8')
    )
    lazy_context_templates = sum(
        1 for path in TEMPLATES.rglob('*.html') if 'page_hero.context_card_body(' in path.read_text(encoding='utf-8')
    )
    blocked_context_templates = sum(
        1 for path in TEMPLATES.rglob('*.html') if 'page_hero.blocked_context_body(' in path.read_text(encoding='utf-8')
    )
    analytics_metadata_templates = sum(
        1 for path in TEMPLATES.rglob('*.html') if 'page_hero.analytics_metadata(' in path.read_text(encoding='utf-8')
    )

    print(
        'KAORI Hero component standard passed: '
        f'{len(primitive_shells)} compatibility Hero shells, '
        f'{len(profile_templates)} canonical profile consumers, '
        f'{audited_descriptions} audited Hero descriptions, '
        f'{context_card_templates} context-card consumers, '
        f'{lazy_context_templates} lazy context bodies, '
        f'{blocked_context_templates} shared blocked contexts, and '
        f'{analytics_metadata_templates} shared Analytics metadata consumers match v1.6; '
        'dashboard parity, blocked readiness ownership, Analytics metadata ownership, description budgets, '
        'implementation, documentation, dark-mode ownership, removed APIs, unmanaged-shell detection, '
        'and quality-gate ownership are synchronized.'
    )


if __name__ == '__main__':
    verify()
