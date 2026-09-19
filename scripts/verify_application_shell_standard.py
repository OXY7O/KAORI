from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def verify() -> None:
    errors: list[str] = []
    navbar = read('app/templates/components/navigation/navbar.html')
    notification_center = read('app/templates/components/navigation/_notification_center.html')
    layout = read('app/templates/layouts/app.html')
    script = read('app/static/js/navbar.js')
    standard = read('docs/design/components/NAVBAR.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        'x-data="kaoriNavbar"' in navbar,
        'Navbar must use the named kaoriNavbar Alpine component.',
        errors,
    )
    require(
        'x-data="{' not in navbar,
        'Navbar must not embed a complex Alpine object literal in x-data.',
        errors,
    )
    require(
        'async refreshNotificationDeck()' not in navbar,
        'Navbar refresh logic must live in app/static/js/navbar.js.',
        errors,
    )
    require(
        '@click="toggleQuickActions()"' in navbar,
        'Quick Actions must use the canonical navbar controller.',
        errors,
    )
    require(
        '@click="toggleUserMenu()"' in navbar,
        'Account menu must use the canonical navbar controller.',
        errors,
    )
    require('@keydown.escape.window="closeMenus()"' in navbar, 'Escape must close all navbar utility surfaces.', errors)
    require(
        'openNotificationDeck(' in notification_center,
        'Notification Deck trigger must use the canonical navbar controller.',
        errors,
    )

    navbar_script = "filename='js/navbar.js'"
    alpine_script = "filename='vendor/alpine/alpine.min.js'"
    require(navbar_script in layout, 'Application layout must load app/static/js/navbar.js.', errors)
    require(alpine_script in layout, 'Application layout must load Alpine.', errors)
    if navbar_script in layout and alpine_script in layout:
        require(
            layout.index(navbar_script) < layout.index(alpine_script),
            'Navbar controller must load before Alpine initializes.',
            errors,
        )

    for token in (
        "document.addEventListener('alpine:init'",
        "window.Alpine.data('kaoriNavbar'",
        'toggleQuickActions()',
        "openNotificationDeck(tab = 'notifications')",
        'toggleUserMenu()',
        'closeMenus()',
        'queueNotificationDeckRefresh()',
        'async refreshNotificationDeck()',
        "credentials: 'same-origin'",
        "cache: 'no-store'",
        'controller.abort()',
    ):
        require(token in script, f'Navbar controller is missing canonical token: {token}', errors)

    for token in (
        '# KAORI Navbar and Application Shell Standard v1.0',
        'x-data="kaoriNavbar"',
        'Exclusive menu state',
        'JavaScript quality gate',
    ):
        require(token in standard, f'Navbar standard documentation is missing: {token}', errors)

    require(
        'python scripts/verify_application_shell_standard.py' in quality_gate,
        'quality_gate.sh must execute the application-shell verifier.',
        errors,
    )
    require(
        'python scripts/verify_javascript_syntax.py' in quality_gate,
        'quality_gate.sh must execute JavaScript syntax verification.',
        errors,
    )

    if errors:
        raise AssertionError('\n'.join(errors))

    print(
        'KAORI application shell standard passed: named Alpine navbar ownership, exclusive Quick/Notification/Account '
        'state, external JavaScript ownership, load ordering, documentation, and release-gate protection are aligned.'
    )


if __name__ == '__main__':
    verify()
