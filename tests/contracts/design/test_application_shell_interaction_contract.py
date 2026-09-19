from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_navbar_uses_named_alpine_component_instead_of_inline_program() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    layout = read('app/templates/layouts/app.html')

    assert 'x-data="kaoriNavbar"' in navbar
    assert 'x-data="{' not in navbar
    assert 'async refreshNotificationDeck()' not in navbar
    assert "filename='js/navbar.js'" in layout
    assert layout.index("filename='js/navbar.js'") < layout.index("filename='vendor/alpine/alpine.min.js'")


def test_quick_notification_and_account_controls_share_one_controller() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    notification_center = read('app/templates/components/navigation/_notification_center.html')
    script = read('app/static/js/navbar.js')

    assert navbar.count('@click="toggleQuickActions()"') == 2
    assert '@click="toggleUserMenu()"' in navbar
    assert '@click="openAbout()"' in navbar
    assert '@keydown.escape.window="closeMenus()"' in navbar
    assert 'openNotificationDeck(' in notification_center
    assert 'toggleQuickActions()' in script
    assert "openNotificationDeck(tab = 'notifications')" in script
    assert 'toggleUserMenu()' in script
    assert 'openAbout()' in script
    assert 'closeMenus()' in script


def test_navbar_javascript_is_syntax_checked() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_javascript_syntax.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI first-party JavaScript syntax passed' in result.stdout


def test_application_shell_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_application_shell_standard.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI application shell standard passed' in result.stdout


def test_application_shell_body_runtime_uses_static_authority() -> None:
    layout = read('app/templates/layouts/app.html')
    runtime = read('app/static/js/application_shell.js')
    detail_rows = read('app/static/js/detail_rows.js')
    runtime_script = "filename='js/application_shell.js'"
    lucide_script = "filename='vendor/lucide/lucide.min.js'"
    pagination_script = "filename='js/pagination.js'"

    assert runtime_script in layout
    assert layout.index(lucide_script) < layout.index(runtime_script) < layout.index(pagination_script)
    assert 'window.renderKaoriIcons' not in layout
    assert 'window.renderLocalOperationalActivities' not in layout
    assert 'window.startOperationalActivity' not in layout
    assert 'window.refreshOperationalTable' not in layout
    assert 'window.prepareInventoryDetail' not in layout

    for token in (
        'window.renderKaoriIcons',
        'window.renderLocalOperationalActivities',
        'window.startOperationalActivity',
        'window.finishOperationalActivity',
        'window.refreshOperationalTable',
        "document.body.addEventListener('htmx:afterSwap'",
        "document.addEventListener('htmx:beforeRequest'",
        "document.addEventListener('submit'",
        "document.getElementById('theme-toggle')",
        "localStorage.setItem('theme'",
    ):
        assert token in runtime

    assert '[data-detail-toggle]' in detail_rows
    assert '.innerHTML =' not in runtime
    assert 'window.kaoriSafeHtml.fragment(html.trim())' in runtime
    assert "loadingIcon.dataset.lucide = 'loader-circle'" in runtime
    assert (
        "progressIndicator.className = 'notification-progress-indeterminate h-full rounded-full bg-kaori-primary'"
        in runtime
    )
    app_sources = [
        *sorted((ROOT / 'app' / 'static' / 'js').rglob('*.js')),
        *sorted((ROOT / 'app' / 'templates').rglob('*.html')),
    ]
    assert all('prepareInventoryDetail' not in path.read_text(encoding='utf-8') for path in app_sources)


def test_prepaint_bootstrap_is_narrowly_governed_outside_inline_debt() -> None:
    app_path = 'app/templates/layouts/app.html'
    auth_path = 'app/templates/layouts/auth.html'
    app = read(app_path)
    auth = read(auth_path)
    baseline = json.loads(read('docs/architecture/ui-inline-debt-baseline.json'))
    verifier = runpy.run_path(str(ROOT / 'scripts' / 'verify_ui_reuse.py'))
    metrics = verifier['_metrics']

    app_marker = 'data-kaori-prepaint-bootstrap="app-shell"'
    auth_marker = 'data-kaori-prepaint-bootstrap="auth-theme"'
    stylesheet = "filename='css/output.css'"

    assert app.count(app_marker) == 1
    assert auth.count(auth_marker) == 1
    assert app.index(app_marker) < app.index(stylesheet)
    assert auth.index(auth_marker) < auth.index(stylesheet)
    assert metrics(app_path, app)['inline_scripts'] == 0
    assert metrics(auth_path, auth)['inline_scripts'] == 0

    extra_runtime = app.replace('</head>', '<script>window.extraRuntime = true</script></head>', 1)
    assert metrics(app_path, extra_runtime)['inline_scripts'] == 1

    expanded_bootstrap = app.replace(
        "document.documentElement.classList.add('dark')",
        "document.documentElement.classList.add('dark'); window.extraRuntime = true",
        1,
    )
    assert metrics(app_path, expanded_bootstrap)['inline_scripts'] == 1

    assert app_path not in baseline['files']
    assert auth_path not in baseline['files']


def test_navbar_controller_exclusively_opens_one_utility_surface() -> None:
    harness = r"""
const listeners = {}
global.document = {
    addEventListener(name, callback) { listeners[name] = callback },
    getElementById() { return null },
    querySelectorAll() { return [] },
}
let factory = null
global.window = {
    Alpine: { data(name, callback) { if (name === 'kaoriNavbar') factory = callback } },
    setInterval() { return 1 },
    clearInterval() {},
    queueMicrotask(callback) { callback() },
}
require('./app/static/js/navbar.js')
listeners['alpine:init']()
const navbar = factory()
navbar.toggleQuickActions()
if (!navbar.quickOpen || navbar.notificationDeckOpen || navbar.userOpen || navbar.aboutOpen) process.exit(10)
navbar.openNotificationDeck('activity')
if (
    navbar.quickOpen ||
    !navbar.notificationDeckOpen ||
    navbar.userOpen ||
    navbar.aboutOpen ||
    navbar.notificationDeckTab !== 'activity'
) process.exit(11)
navbar.toggleUserMenu()
if (navbar.quickOpen || navbar.notificationDeckOpen || !navbar.userOpen || navbar.aboutOpen) process.exit(12)
navbar.openAbout()
if (navbar.quickOpen || navbar.notificationDeckOpen || navbar.userOpen || !navbar.aboutOpen) process.exit(13)
navbar.closeMenus()
if (navbar.quickOpen || navbar.notificationDeckOpen || navbar.userOpen || navbar.aboutOpen) process.exit(14)
"""
    result = subprocess.run(
        ['node', '-e', harness],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
