from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
NAVIGATION_DIR = ROOT / 'app' / 'templates' / 'components' / 'navigation'
PAGE_HERO = ROOT / 'app' / 'templates' / 'components' / 'page_hero.html'

PARENT_NAVIGATION_TEMPLATES = (
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
    'sidebar.html',
)


def _sidebar_parent_blocks(source: str) -> list[str]:
    blocks: list[str] = []
    search_from = 0

    while True:
        marker = source.find('sidebar-parent-link', search_from)
        if marker == -1:
            return blocks

        summary_start = source.rfind('<summary', 0, marker)
        anchor_start = source.rfind('<a ', 0, marker)
        block_start = max(summary_start, anchor_start)

        if block_start == -1:
            raise AssertionError('sidebar-parent-link is not inside a summary or anchor element')

        if block_start == summary_start:
            closing_tag = '</summary>'
        else:
            closing_tag = '</a>'

        block_end = source.find(closing_tag, marker)
        if block_end == -1:
            raise AssertionError(f'Missing {closing_tag} for sidebar parent link')

        block_end += len(closing_tag)
        blocks.append(source[block_start:block_end])
        search_from = block_end


def test_sidebar_parent_navigation_uses_larger_type_than_children() -> None:
    for filename in PARENT_NAVIGATION_TEMPLATES:
        source = (NAVIGATION_DIR / filename).read_text(encoding='utf-8')
        parent_blocks = _sidebar_parent_blocks(source)

        assert parent_blocks, f'No sidebar parent link found in {filename}'
        for block in parent_blocks:
            assert 'text-base' in block, filename
            assert 'font-semibold' in block, filename
            assert 'leading-6' in block, filename
            assert 'text-sm' not in block, filename
            assert 'leading-5' not in block, filename

    submenu_sources = '\n'.join(
        (NAVIGATION_DIR / filename).read_text(encoding='utf-8') for filename in PARENT_NAVIGATION_TEMPLATES
    )
    assert 'sidebar-submenu' in submenu_sources
    assert 'py-1.5 text-sm' in submenu_sources
    assert 'py-1.5 text-xs' not in submenu_sources


def test_page_hero_description_is_one_type_step_above_supporting_copy() -> None:
    source = PAGE_HERO.read_text(encoding='utf-8')
    macro_start = source.index('{% macro description_classes()')
    macro_end = source.index('{%- endmacro %}', macro_start)
    description_macro = source[macro_start:macro_end]

    assert 'text-base' in description_macro
    assert 'leading-7' in description_macro
    assert 'text-sm' not in description_macro
