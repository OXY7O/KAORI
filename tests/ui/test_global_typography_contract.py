from pathlib import Path
import re

TEMPLATES = Path('app/templates')


def _source() -> str:
    return '\n'.join(path.read_text(encoding='utf-8') for path in TEMPLATES.rglob('*.html'))


def test_unsupported_arbitrary_font_sizes_are_absent():
    source = _source()
    for token in ('text-[9px]', 'text-[11px]', 'text-[12px]', 'text-[13px]', 'text-[14px]', 'text-[15px]', 'text-[30px]', 'text-[32px]'):
        assert token not in source


def test_bold_is_not_the_default_content_emphasis():
    assert 'font-bold' not in _source()


def test_heading_and_form_roles_do_not_force_css_casing():
    pattern = re.compile(r'<(?:h[1-6]|label|legend|thead)\b[^>]*class=["\'][^"\']*(?:uppercase|capitalize|lowercase)', re.I)
    assert not pattern.search(_source())


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
