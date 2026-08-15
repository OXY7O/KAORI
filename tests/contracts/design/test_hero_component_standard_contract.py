from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_hero_component_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_hero_component_standard.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI Hero component standard passed' in result.stdout


def test_hero_documentation_has_one_global_contract_and_one_domain_extension() -> None:
    components = ROOT / 'docs' / 'design' / 'components'
    global_standard = (components / 'HERO.md').read_text(encoding='utf-8')
    analytics_extension = (components / 'ANALYTICS_HERO.md').read_text(encoding='utf-8')

    assert 'KAORI Hero Component Standard v1.5' in global_standard
    assert '16 px, regular, 28 px line height' in global_standard
    assert 'Action Icon Box' in global_standard
    assert 'Context Icon Box' in global_standard
    assert 'Status Badge Box' in global_standard
    assert 'exactly two compact metrics' in global_standard
    assert 'kaori-hero-shell' in global_standard
    assert 'components/DARK_MODE.md' in global_standard
    assert 'Kubernetes Analytics Hero Extension' in analytics_extension
    assert not (components / 'ANALYTICS_HERO_STANDARD.md').exists()
    assert not (components / 'ANALYTICS_HERO_INVENTORY_REFERENCE.md').exists()


def test_removed_hero_macros_are_absent_from_implementation() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    for macro in (
        'context_posture_header',
        'context_posture_note',
        'context_bottom_notice',
        'action_group_classes',
        'secondary_action_classes',
        'destructive_action_classes',
        'supporting_strip',
    ):
        assert f'macro {macro}' not in source


def test_hero_right_header_accessories_have_three_canonical_variants() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')

    assert 'macro context_action_icon_box(icon, href, aria_label, title=None)' in source
    assert 'macro context_icon_box(icon)' in source
    assert "macro context_header_status(eyebrow_label, title, status_label, status_tone='info')" in source
    assert 'aria-label="{{ aria_label }}"' in source
    assert 'context_status_badge(status_label, status_tone)' in source

def test_hero_context_panel_footer_variants_share_one_precise_row_rhythm() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')

    assert 'flex h-full min-h-[13rem] flex-col gap-3' in source
    assert 'grid grid-cols-2 auto-rows-fr gap-2' in source
    assert 'kaori-hero-tile mt-auto flex min-h-10 items-center gap-2' in source
    assert "mt-auto grid min-h-10 gap-2 {{ 'grid-cols-2' if columns == 2 else 'grid-cols-1' }}" in source
    assert 'mt-3 grid grid-cols-2 gap-2' not in source
    assert 'mt-auto grid gap-2 pt-3' not in source

