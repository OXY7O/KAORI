"""KAORI offline HTML source verifier counts only executable inline scripts."""

import pytest

from scripts.verify_ui_reuse import _APPROVED_PREPAINT_BOOTSTRAPS, _metrics


def test_ui_reuse_ignores_inert_json_bootstrap_script() -> None:
    source = '<script id="bootstrap" type="application/json">{"ready": true}</script>'

    assert _metrics('app/templates/example.html', source)['inline_scripts'] == 0


def test_ui_reuse_still_counts_executable_inline_script() -> None:
    source = '<script>window.kaoriReady = true</script>'

    assert _metrics('app/templates/example.html', source)['inline_scripts'] == 1


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ('<script data-hint=">" src="/js/app.js"></script>', 0),
        ('<script data-hint=">" type="application/json">{"ready": true}</script>', 0),
        ('<script data-hint=">" type="module">window.kaoriReady = true</script>', 1),
        ('<script data-hint=">">window.kaoriReady = true</script>', 1),
        ('<script data-hint=">" src="/js/app.js">', 0),
    ],
)
def test_ui_reuse_parses_quoted_tag_closers_without_false_inline_debt(
    source: str,
    expected: int,
) -> None:
    assert _metrics('app/templates/example.html', source)['inline_scripts'] == expected


def _app_shell_prepaint_source(body: str) -> str:
    return (
        '<head><script data-kaori-prepaint-bootstrap="app-shell">'
        + body
        + '</script>'
        + '<link href="{{ url_for('
        + "'static', filename='css/output.css'"
        + ') }}" rel="stylesheet"></head>'
    )


def test_ui_reuse_preserves_exact_app_shell_prepaint_exemption() -> None:
    body = str(_APPROVED_PREPAINT_BOOTSTRAPS['app/templates/layouts/app.html']['body'])
    source = _app_shell_prepaint_source(body)

    assert _metrics('app/templates/layouts/app.html', source)['inline_scripts'] == 0
    assert _metrics('app/templates/other.html', source)['inline_scripts'] == 1


def test_ui_reuse_counts_tampered_or_duplicate_app_shell_prepaint() -> None:
    body = str(_APPROVED_PREPAINT_BOOTSTRAPS['app/templates/layouts/app.html']['body'])
    modified = _app_shell_prepaint_source(body.replace("const theme =", "const compromisedTheme ="))
    duplicate = _app_shell_prepaint_source(body).replace(
        '</head>',
        '<script data-kaori-prepaint-bootstrap="app-shell">' + body + '</script></head>',
    )

    assert _metrics('app/templates/layouts/app.html', modified)['inline_scripts'] == 1
    assert _metrics('app/templates/layouts/app.html', duplicate)['inline_scripts'] == 2
