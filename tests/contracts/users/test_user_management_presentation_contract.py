from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_user_management_labels_use_title_case():
    content = read('app/templates/users/partials/_summary_cards.html') + read(
        'app/templates/users/partials/_filters.html'
    )
    for label in ('Credential Owner: KAORI', 'Access Path: Directory Provisioning', 'Search User', 'Identity Source'):
        assert label in content
    for legacy in ('Credential owner: KAORI', 'Access path: Directory Provisioning', 'Search user', 'Identity source'):
        assert legacy not in content


def test_disabled_pagination_is_not_an_htmx_anchor():
    content = read('app/templates/users/partials/_table.html')
    assert '{% if pagination.has_prev %}' in content
    assert '{% if pagination.has_next %}' in content
    assert content.count('aria-disabled="true"') >= 2
    assert 'class="{{ pagination_ui.navigation_classes(disabled=true) }}" aria-disabled="true"' in content
