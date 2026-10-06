from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEMgrep = ROOT / '.github/ci/semgrep.yml'
SAFE_HTML = ROOT / 'app/static/js/safe_html.js'
APP_LAYOUT = ROOT / 'app/templates/layouts/app.html'
AFFECTED_JAVASCRIPT = (
    ROOT / 'app/static/js/detail_rows.js',
    ROOT / 'app/static/js/navbar.js',
    ROOT / 'app/static/js/secret_reveal_value.js',
)


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_direct_innerhtml_assignment_remains_blocked() -> None:
    source = read(SEMgrep)
    assert 'kaori-javascript-innerhtml-assignment' in source
    assert 'pattern: $ELEMENT.innerHTML = $VALUE' in source


def test_reviewed_javascript_surfaces_have_no_direct_innerhtml_assignment() -> None:
    for path in AFFECTED_JAVASCRIPT:
        assert '.innerHTML =' not in read(path), path


def test_server_fragment_helper_sanitizes_executable_markup() -> None:
    source = read(SAFE_HTML)
    for token in (
        'DOMParser',
        'script, iframe, object, embed',
        "startsWith('on')",
        'javascript:',
        'replaceChildren',
        'window.kaoriSafeHtml',
    ):
        assert token in source


def test_safe_html_helper_loads_before_dynamic_fragment_consumers() -> None:
    source = read(APP_LAYOUT)
    safe_html = "filename='js/safe_html.js'"
    navbar = "filename='js/navbar.js'"
    detail_rows = "filename='js/detail_rows.js'"

    assert safe_html in source
    assert source.index(safe_html) < source.index(navbar)
    assert source.index(safe_html) < source.index(detail_rows)
