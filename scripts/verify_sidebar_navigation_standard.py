from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVIGATION_DIR = ROOT / 'app' / 'templates' / 'components' / 'navigation'
SIDEBAR = NAVIGATION_DIR / 'sidebar.html'
STANDARD = ROOT / 'docs' / 'design' / 'components' / 'SIDEBAR_NAVIGATION.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'

MENU_TEMPLATES = (
    'access_management_menu.html',
    'analytics_menu.html',
    'dashboards_menu.html',
    'governance_menu.html',
    'integrations_menu.html',
    'intelligence_menu.html',
    'inventory_menu.html',
    'kubernetes_operations_menu.html',
    'platform_operations_menu.html',
    'reports_menu.html',
    'settings_menu.html',
)

EXPECTED_SECTION_ORDER = (
    'Main',
    'Kubernetes',
    'Insights &amp; Reporting',
    'Platform Extensions',
    'Platform Operations',
    'Administration',
)

EXPECTED_INCLUDE_ORDER = (
    'dashboards_menu.html',
    'inventory_menu.html',
    'kubernetes_operations_menu.html',
    'governance_menu.html',
    'analytics_menu.html',
    'intelligence_menu.html',
    'reports_menu.html',
    'integrations_menu.html',
    'platform_operations_menu.html',
    'access_management_menu.html',
    'settings_menu.html',
)

PARENT_TOKENS = (
    'sidebar-parent-link',
    'min-h-11',
    'rounded-lg',
    'px-2.5',
    'py-2',
    'text-base',
    'font-semibold',
    'leading-6',
    '[.sidebar-collapsed_&]:justify-center',
    '[.sidebar-collapsed_&]:px-2',
    'sidebar-parent-active',
    'sidebar-item-idle',
)

SUBMENU_TOKENS = (
    'group',
    'flex',
    'items-center',
    'gap-2',
    'rounded-lg',
    'px-2.5',
    'py-1.5',
    'text-sm',
    'leading-5',
    'transition',
    'bg-white/[0.08]',
    'text-kaori-accent',
    'sidebar-item-idle',
    'h-1.5 w-1.5',
    'h-3.5 w-3.5',
    'truncate whitespace-nowrap',
)


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f'Missing required sidebar contract file: {path.relative_to(ROOT)}')
    return path.read_text(encoding='utf-8')


def _parent_blocks(source: str, filename: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    search_from = 0

    while True:
        marker = source.find('sidebar-parent-link', search_from)
        if marker == -1:
            return blocks

        summary_start = source.rfind('<summary', 0, marker)
        anchor_start = source.rfind('<a ', 0, marker)
        block_start = max(summary_start, anchor_start)
        if block_start == -1:
            raise AssertionError(f'{filename}: sidebar-parent-link has no summary or anchor owner')

        tag = 'summary' if block_start == summary_start else 'a'
        closing = f'</{tag}>'
        block_end = source.find(closing, marker)
        if block_end == -1:
            raise AssertionError(f'{filename}: parent block is missing {closing}')

        block_end += len(closing)
        blocks.append((tag, source[block_start:block_end]))
        search_from = block_end


def _submenu_links(source: str, filename: str) -> list[str]:
    marker = source.find('sidebar-submenu')
    if marker == -1:
        raise AssertionError(f'{filename}: missing sidebar-submenu container')
    return re.findall(r'<a\s[\s\S]*?</a>', source[marker:])


def _require_tokens(block: str, tokens: tuple[str, ...], owner: str) -> None:
    missing = [token for token in tokens if token not in block]
    if missing:
        raise AssertionError(f'{owner}: missing canonical tokens: {", ".join(missing)}')


def verify() -> None:
    sidebar = _read(SIDEBAR)
    standard = _read(STANDARD)

    _require_tokens(
        sidebar,
        (
            'w-[250px]',
            '[.sidebar-collapsed_&]:w-[78px]',
            'rounded-2xl',
            'bg-surface-sidebar',
            'overflow-y-auto',
            'sidebar-expanded-only',
            'text-sm font-extrabold leading-5',
            'text-xs font-medium',
        ),
        'sidebar frame and brand',
    )

    section_pattern = re.compile(
        r'<div class="sidebar-expanded-only mb-1\.5 px-3 sidebar-section-label '
        r'text-xs font-extrabold uppercase tracking-widest">([^<]+)</div>'
    )
    section_order = tuple(match.strip() for match in section_pattern.findall(sidebar))
    if section_order != EXPECTED_SECTION_ORDER:
        raise AssertionError(
            f'sidebar.html: canonical section order changed. Expected {EXPECTED_SECTION_ORDER}, found {section_order}'
        )

    include_positions: list[int] = []
    for filename in EXPECTED_INCLUDE_ORDER:
        marker = f'components/navigation/{filename}'
        position = sidebar.find(marker)
        if position == -1:
            raise AssertionError(f'sidebar.html: missing canonical include {filename}')
        include_positions.append(position)
    if include_positions != sorted(include_positions):
        raise AssertionError('sidebar.html: canonical parent-menu include order changed')

    sources = {filename: _read(NAVIGATION_DIR / filename) for filename in MENU_TEMPLATES}
    sources['sidebar.html'] = sidebar

    parent_count = 0
    submenu_count = 0
    for filename, source in sources.items():
        blocks = _parent_blocks(source, filename)
        if not blocks:
            raise AssertionError(f'{filename}: no canonical parent navigation block found')

        for tag, block in blocks:
            parent_count += 1
            _require_tokens(block, PARENT_TOKENS, f'{filename} parent')
            _require_tokens(
                block,
                (
                    'h-8 w-8',
                    'h-4 w-4',
                    'truncate whitespace-nowrap',
                    'sidebar-parent-active-icon',
                    'sidebar-item-idle-icon',
                ),
                f'{filename} parent identity',
            )
            if 'text-sm' in block or 'text-xs' in block or 'text-[' in block:
                raise AssertionError(f'{filename}: parent typography must remain text-base')
            if 'title="' not in block or 'aria-label="' not in block:
                raise AssertionError(f'{filename}: each parent requires title and aria-label')
            if tag == 'summary':
                _require_tokens(
                    block,
                    (
                        'cursor-pointer',
                        'select-none',
                        'justify-between',
                        'sidebar-menu-chevron',
                        '@click=',
                        'toggleSidebar()',
                    ),
                    f'{filename} expandable parent',
                )

        if filename == 'sidebar.html':
            continue

        if '<details class="sidebar-menu space-y-1"' not in source:
            raise AssertionError(f'{filename}: expandable parent must use sidebar-menu space-y-1')
        if 'sidebar-expanded-only sidebar-submenu ml-6 mt-1 space-y-1 border-l border-white/10 pl-3' not in source:
            raise AssertionError(f'{filename}: submenu container geometry changed')

        links = _submenu_links(source, filename)
        if not links:
            raise AssertionError(f'{filename}: parent menu has no submenu links')
        for index, link in enumerate(links, start=1):
            submenu_count += 1
            _require_tokens(link, SUBMENU_TOKENS, f'{filename} submenu #{index}')
            if 'text-base' in link or 'text-xs' in link or 'text-[' in link:
                raise AssertionError(f'{filename} submenu #{index}: submenu typography must remain text-sm')

    doc_tokens = (
        '# KAORI Sidebar Navigation Standard v1.2',
        'Status:** Locked application-shell and dark-mode contract',
        'Parent menu label | 16 px',
        'Submenu label | 14 px',
        'Parent:  min-h-11 rounded-lg px-2.5 py-2 text-base font-semibold leading-6',
        'Child:   rounded-lg px-2.5 py-1.5 text-sm leading-5',
        'sidebar-parent-active',
        'dark mode keeps the active Violet surface without a separate left-edge accent',
        '## Canonical Information Architecture',
        '## Enforcement and Change Control',
        'scripts/verify_sidebar_navigation_standard.py',
        'tests/contracts/design/test_sidebar_navigation_standard_contract.py',
    )
    _require_tokens(standard, doc_tokens, 'sidebar standard documentation')

    quality_gate = _read(QUALITY_GATE)
    if 'python scripts/verify_sidebar_navigation_standard.py' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not execute the sidebar standard verifier')

    print(
        'KAORI sidebar navigation standard passed: '
        f'{parent_count} parent blocks and {submenu_count} submenu links conform to v1.2; '
        'section order, collapse behavior, accessibility, typography, and documentation are locked.'
    )


if __name__ == '__main__':
    verify()
