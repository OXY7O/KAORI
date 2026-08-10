from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT / 'docs' / 'standards' / 'KAORI_ENGINEERING_STANDARD_V1.md'
DESIGN_SYSTEM = ROOT / 'docs' / 'design' / 'KAORI_DESIGN_SYSTEM.md'
DESIGN_README = ROOT / 'docs' / 'design' / 'README.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'

REQUIRED_COMPONENT_DOCUMENTS = (
    'COLOR_AND_SEMANTIC.md',
    'DARK_MODE.md',
    'TYPOGRAPHY.md',
    'HERO.md',
    'TABLE_AND_LABEL.md',
    'PAGINATION.md',
    'RIGHT_CONTEXT_RAIL.md',
    'TAB_STYLES.md',
    'VIEW_MORE_CONTENT.md',
    'MODAL_DRAWER.md',
    'SIDE_DRAWER.md',
    'BUTTON.md',
    'LOADING.md',
    'OPERATIONAL_ACTION_FEEDBACK.md',
    'NAVBAR.md',
    'SIDEBAR_NAVIGATION.md',
    'ACCESSIBILITY.md',
    'RESPONSIVE_AND_HTMX.md',
    'EMPTY_ERROR_STATE.md',
)

REQUIRED_STANDARD_SECTIONS = (
    '## 1. Brand, color, theme, and typography',
    '## 2. Hero',
    'Action Icon Box',
    'Context Icon Box',
    'Status Badge Box',
    '## 3. Tables, status labels, and pagination',
    '## 4. Right-side content rail',
    '## 5. Tabs',
    '## 6. Progressive disclosure and detail content',
    '## 8. Loading, toast, and operational feedback',
    '## 9. Notification style',
    '## 10. Application shell, navbar, and sidebar',
    '## 11. Accessibility',
    '## 15. Security and reliability',
    '## 16. Testing and release evidence',
    '## 17. Per-page final recheck checklist',
    'PASS — LOCKED',
)


def verify() -> None:
    standard = STANDARD.read_text(encoding='utf-8')
    design_system = DESIGN_SYSTEM.read_text(encoding='utf-8')
    design_readme = DESIGN_README.read_text(encoding='utf-8')
    quality_gate = QUALITY_GATE.read_text(encoding='utf-8')

    missing_sections = [token for token in REQUIRED_STANDARD_SECTIONS if token not in standard]
    if missing_sections:
        raise AssertionError(f'Engineering standard is missing required guidance: {", ".join(missing_sections)}')

    component_root = ROOT / 'docs' / 'design' / 'components'
    missing_documents = [name for name in REQUIRED_COMPONENT_DOCUMENTS if not (component_root / name).exists()]
    if missing_documents:
        raise AssertionError(
            f'Engineering standard references missing component contracts: {", ".join(missing_documents)}'
        )

    standard_ref = 'docs/standards/KAORI_ENGINEERING_STANDARD_V1.md'
    if standard_ref not in design_system:
        raise AssertionError('KAORI Design System must register the Engineering Standard as the final-recheck index.')
    if '../standards/KAORI_ENGINEERING_STANDARD_V1.md' not in design_readme:
        raise AssertionError('Design documentation README must direct reviewers to the Engineering Standard.')
    if 'python scripts/verify_engineering_standard.py' not in quality_gate:
        raise AssertionError('quality_gate.sh must execute the Engineering Standard verifier.')

    print(
        'KAORI Engineering Standard v1 passed: global component guidance, Hero accessory registry, shell, '
        'accessibility, security, test-evidence, and per-page final-recheck ownership are registered.'
    )


if __name__ == '__main__':
    verify()
