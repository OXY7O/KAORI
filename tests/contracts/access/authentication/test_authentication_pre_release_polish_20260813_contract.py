from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_login_theme_toggle_exposes_the_next_theme_action() -> None:
    login = read('app/templates/access/authentication/partials/_login_form.html')
    runtime = read('app/static/js/auth_login.js')

    assert 'aria-label="Switch to Dark Mode"' in login
    assert 'title="Switch to Dark Mode"' in login
    assert 'const actionLabel = `Switch to ${nextTheme} Mode`' in runtime
    assert "themeToggle.setAttribute('aria-label', actionLabel)" in runtime
    assert "themeToggle.setAttribute('title', actionLabel)" in runtime


def test_authentication_release_labels_keep_kaori_title_case() -> None:
    index = read('app/templates/access/authentication/index.html')
    setup = read('app/templates/access/authentication/setup_required.html')

    assert '{% block title %}Sign In · KAORI{% endblock title %}' in index
    for token in (
        'Run the Initial KAORI Database Bootstrap',
        'Manual Initialization Commands',
        'Encryption Key Requirement',
        'Missing Schema Objects',
        'PostgreSQL Is Unavailable',
    ):
        assert token in setup
