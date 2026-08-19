from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_terminal_command_owns_copyable_command_chrome_across_shells() -> None:
    component = read('app/templates/components/terminal_command.html')
    runtime = read('app/static/js/clipboard.js')
    app_layout = read('app/templates/layouts/app.html')
    auth_layout = read('app/templates/layouts/auth.html')
    standard = read('docs/design/components/TERMINAL_COMMAND.md')

    for token in (
        'data-kaori-terminal-command',
        'data-kaori-copy-root',
        'data-kaori-copy-button',
        'data-kaori-copy-source',
        'data-kaori-copy-label',
        'aria-live="polite"',
    ):
        assert token in component

    assert 'x-data=' not in component
    assert '@click=' not in component
    assert 'navigator.clipboard?.writeText' in runtime
    assert "document.execCommand('copy')" in runtime
    assert "closest('[data-kaori-copy-button]')" in runtime
    assert "filename='js/clipboard.js'" in app_layout
    assert "filename='js/clipboard.js'" in auth_layout
    assert 'shared component standard' in standard
    assert 'must not require Alpine or HTMX' in standard
