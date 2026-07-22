from pathlib import Path
import re

TEMPLATES = Path('app/templates')


def _source() -> str:
    return '\n'.join(path.read_text(encoding='utf-8') for path in TEMPLATES.rglob('*.html'))


def test_design_system_documents_exist():
    required = [
        'docs/design/DESIGN_SYSTEM.md',
        'docs/design/components/TYPOGRAPHY.md',
        'docs/design/components/CARD.md',
        'docs/design/components/FORM.md',
        'docs/design/components/LOADING.md',
        'docs/design/components/EMPTY_ERROR_STATE.md',
        'docs/design/components/MODAL_DRAWER.md',
        'docs/design/components/EXPANDABLE.md',
        'docs/design/components/ICONS.md',
        'docs/design/components/SPACING.md',
        'docs/design/components/ACCESSIBILITY.md',
        'docs/design/components/RESPONSIVE_AND_HTMX.md',
    ]
    for item in required:
        assert Path(item).is_file(), item
