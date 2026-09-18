import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_settings_final_lock_is_release_gated_and_documented() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    readme = read('app/settings/README.md')
    lock = read('docs/design/KAORI_SETTINGS_LOCK_V1.md')

    assert 'python scripts/verify_settings_final_lock.py' in quality_gate
    assert 'Settings v1 is final-locked' in readme
    assert 'Status: **FINAL LOCKED**' in lock
    assert 'General Settings' in lock
    assert 'Account & Authentication' in lock


def test_settings_final_lock_retires_obsolete_side_context_partials() -> None:
    for relative in (
        'app/templates/settings/general/partials/_impact_information.html',
        'app/templates/settings/account/partials/_profile_information.html',
        'app/templates/settings/account/partials/_activity_information.html',
    ):
        assert not (ROOT / relative).exists()


def test_settings_active_surfaces_avoid_page_local_style_drift() -> None:
    for path in sorted((ROOT / 'app/templates/settings').rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        assert 'text-[10px]' not in source
        assert 'tracking-[' not in source
        assert 'font-extrabold' not in source
        assert ' border-red-' not in source
        assert ' bg-red-' not in source
        assert ' text-red-' not in source

def test_settings_query_tabs_delegate_to_shared_htmx_tab_authority() -> None:
    general_path = 'app/templates/settings/general/partials/_tabs.html'
    account_path = 'app/templates/settings/account/partials/_tabs.html'
    shared_path = 'app/templates/components/workspace_tabs.html'

    general = read(general_path)
    account = read(account_path)
    shared = read(shared_path)
    verifier = read('scripts/verify_settings_final_lock.py')
    baseline = json.loads(read('docs/architecture/ui-style-debt-baseline.json'))

    assert "macro render_query_tabs(" in shared
    assert 'data-kaori-tab-variant="query-backed-htmx"' in shared
    assert 'class="flex gap-2 overflow-x-auto"' in shared
    assert 'role="tablist"' in shared
    assert 'role="tab"' in shared
    assert 'hx-get="{{ tab_href }}"' in shared
    assert 'hx-target="{{ hx_target }}"' in shared
    assert 'hx-indicator="{{ hx_indicator }}"' in shared
    assert 'hx-sync="{{ hx_sync }}"' in shared
    assert 'hx-swap="outerHTML"' in shared
    assert 'hx-push-url="true"' in shared
    assert "aria-selected="{{ 'true' if active_key == tab_key else 'false' }}"" in shared

    for path, source in ((general_path, general), (account_path, account)):
        assert '{% import "components/workspace_tabs.html" as workspace_tabs %}' in source, path
        assert 'workspace_tabs.render_query_tabs(' in source, path
        assert 'role="tablist"' not in source, path
        assert 'flex gap-2 overflow-x-auto' not in source, path
        assert path not in baseline['files']

    assert "hx_target='#general-settings-page'" in general
    assert "hx_indicator='#general-settings-loading'" in general
    assert "hx_sync='#general-settings-page:replace'" in general
    assert "hx_target='#account-authentication-page'" in account
    assert "hx_indicator='#account-settings-loading'" in account
    assert "hx_sync='#account-authentication-page:replace'" in account

    assert "workspace_tabs = read('app/templates/components/workspace_tabs.html')" in verifier
    assert "render_query_tabs" in verifier
    assert "query-backed-htmx" in verifier

