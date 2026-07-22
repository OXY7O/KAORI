from pathlib import Path

TEMPLATES = Path('app/templates')


def _hero_templates():
    for path in TEMPLATES.rglob('*.html'):
        text = path.read_text(encoding='utf-8')
        if 'page_hero.layout_classes()' in text:
            yield path, text


def test_shared_layout_uses_explicit_seven_five_columns():
    failures = []
    for path, text in _hero_templates():
        has_content = 'page_hero.content_classes()' in text or 'xl:col-span-7' in text
        has_aside = 'page_hero.aside_classes()' in text or 'xl:col-span-5' in text
        if not (has_content and has_aside):
            failures.append(str(path))
    assert not failures, f'Hero layout is missing explicit 7/5 columns: {failures}'


def test_integrations_overview_does_not_embed_legacy_posture_card():
    path = TEMPLATES / 'integrations/partials/_hero.html'
    text = path.read_text(encoding='utf-8')
    assert 'page_hero.content_classes()' in text
    assert 'page_hero.aside_classes()' in text
    assert 'Ready integration targets' not in text
    assert 'sm:max-w-[360px]' not in text
    assert 'xl:w-[360px]' not in text


def test_reaudited_hero_files_do_not_start_with_dangling_closing_div():
    paths = [
        TEMPLATES / 'reports/overview/index.html',
        TEMPLATES / 'reports/generate/index.html',
        TEMPLATES / 'reports/generated/index.html',
        TEMPLATES / 'reports/report_templates/index.html',
    ]
    for path in paths:
        text = path.read_text(encoding='utf-8')
        marker = '<section class="{{ page_hero.shell_classes() }}">'
        hero = text.split(marker, 1)[1].lstrip()
        assert not hero.startswith('</div>'), f'Dangling closing div remains in {path}'


