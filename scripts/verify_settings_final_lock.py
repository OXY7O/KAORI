#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCK_DOCS = (
    'docs/design/KAORI_SETTINGS_LOCK_V1.md',
    'docs/design/audits/KAORI_SETTINGS_FINAL_LOCK_AUDIT_2026_08_11.md',
)

RETIRED_PARTIALS = (
    'app/templates/settings/general/partials/_impact_information.html',
    'app/templates/settings/account/partials/_profile_information.html',
    'app/templates/settings/account/partials/_activity_information.html',
)

RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border|ring|shadow|fill|stroke)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|purple|'
    r'violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
    r'\d{2,3}(?:/\d{1,3})?\b'
)
ARBITRARY_TEXT = re.compile(r'\btext-\[[^\]]+\]')
ARBITRARY_TRACKING = re.compile(r'\btracking-\[[^\]]+\]')
INLINE_STYLE = re.compile(r'\bstyle\s*=', re.I)
INLINE_HANDLER = re.compile(r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=', re.I)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    templates = sorted((ROOT / 'app/templates/settings').rglob('*.html'))
    require(bool(templates), 'Settings templates are missing', errors)

    for path in templates:
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        require(not RAW_HEX.search(source), f'{relative}: raw hex color is forbidden', errors)
        require(not RAW_PALETTE.search(source), f'{relative}: raw Tailwind palette utility is forbidden', errors)
        require(not ARBITRARY_TEXT.search(source), f'{relative}: arbitrary text size is forbidden', errors)
        require(not ARBITRARY_TRACKING.search(source), f'{relative}: arbitrary tracking is forbidden', errors)
        require('font-extrabold' not in source, f'{relative}: font-extrabold is forbidden', errors)
        require(' uppercase ' not in f' {source} ', f'{relative}: visible uppercase utility is forbidden', errors)
        require(not INLINE_STYLE.search(source), f'{relative}: inline style is forbidden', errors)
        require(not INLINE_HANDLER.search(source), f'{relative}: inline DOM handler is forbidden', errors)

    for relative in RETIRED_PARTIALS:
        require(not (ROOT / relative).exists(), f'retired Settings partial reintroduced: {relative}', errors)
    for relative in LOCK_DOCS:
        require((ROOT / relative).exists(), f'missing Settings lock artifact: {relative}', errors)

    routes = read('app/settings/routes.py')
    readme = read('app/settings/README.md')
    quality_gate = read('scripts/quality_gate.sh')
    system_information = read('app/settings/system_information.py')
    timezone_js = read('app/static/js/user_timezone_sync.js')

    for required in (
        "@bp.route('/general', methods=['GET', 'POST'])",
        '@login_required',
        "user.has_permission('system.view')",
        "allowed_tabs = {'time-locale', 'regional-format'}",
        "OperationalDeliveryPolicy.AUDIT_ONLY",
        "'kaori:general-settings-saved'",
        "@bp.post('/general/browser-timezone')",
    ):
        require(required in routes, f'General Settings contract missing: {required}', errors)

    for required in (
        "'X-CSRFToken': csrfToken",
        "credentials: 'same-origin'",
        "Intl.DateTimeFormat().resolvedOptions().timeZone",
    ):
        require(required in timezone_js, f'Browser timezone security contract missing: {required}', errors)

    for forbidden in (
        'DATABASE_URL',
        'REDIS_URL',
        'SECRET_KEY',
        'CLIENT_SECRET',
        'BIND_PASSWORD',
        'KUBECONFIG',
    ):
        require(
            forbidden not in system_information,
            f'System Information may expose sensitive config key: {forbidden}',
            errors,
        )

    general_page = read('app/templates/settings/general/partials/_page_content.html')
    timezone = read('app/templates/settings/general/partials/_time_locale.html')
    regional = read('app/templates/settings/general/partials/_regional_format.html')
    general_tabs = read('app/templates/settings/general/partials/_tabs.html')
    for required in (
        'settings/general/partials/_hero.html',
        'settings/general/partials/_tabs.html',
        'data-timezone-workspace-layout="full-width"',
        'data-regional-format-workspace-layout="full-width"',
    ):
        require(required in general_page, f'General Settings composition missing: {required}', errors)
    for source, label in ((timezone, 'Time Zone'), (regional, 'Regional Format')):
        require('Preference Scope &amp; Boundary' in source, f'{label} preference boundary missing', errors)
        require('Display preference only.' in source, f'{label} data/execution boundary missing', errors)
        require('components/operational_callout.html' in source if label == 'Time Zone' else True,
                f'{label} semantic feedback must use shared callout ownership', errors)
    require('flex gap-2 overflow-x-auto' in general_tabs, 'General Settings tab contract drifted', errors)

    account_page = read('app/templates/settings/account/partials/_page_content.html')
    account_tabs = read('app/templates/settings/account/partials/_tabs.html')
    profile = read('app/templates/settings/account/partials/_profile_cards.html')
    activity = read('app/templates/settings/account/partials/_recent_login_activity.html')
    credentials = read('app/templates/settings/account/partials/_change_password.html')
    credential_context = read('app/templates/settings/account/partials/_credential_information.html')

    for required in (
        "@bp.route('/account', methods=['GET', 'POST'])",
        "can_change_password = auth_source == 'database'",
        'preserve_current_session_after_password_change(user)',
        "reason_code='current_password_mismatch'",
        "reason_code='current_password_reuse'",
        "'session_effect': 'other_sessions_revoked'",
        "'remembered_sign_ins': 'revoked'",
    ):
        require(required in routes, f'Account security contract missing: {required}', errors)
    require('flex gap-2 overflow-x-auto' in account_tabs, 'Account tab contract drifted', errors)
    require('data-account-profile-workspace="full-width"' in profile, 'Account Profile must remain full-width', errors)
    require('Last Verified Sign-In' in profile, 'Account Profile sign-in evidence missing', errors)
    require('components/table.html' in activity, 'Authentication Activity must use shared table', errors)
    require('components/table_label.html' in activity, 'Authentication Activity must use shared status labels', errors)
    require(
        'data-authentication-evidence-boundary="inline"' in activity,
        'Authentication evidence boundary missing',
        errors,
    )
    require(
        'components/operational_callout.html' in credentials,
        'Credential feedback must use shared semantic ownership',
        errors,
    )
    require(
        'data-credential-workspace-layout="natural-columns"' in account_page,
        'Credential layout contract drifted',
        errors,
    )
    require(
        'data-credential-security-panel="single-context-box"' in credential_context,
        'Credential security context drifted',
        errors,
    )

    for required in (
        'Settings v1 is final-locked',
        'General Settings presentation contract',
        'Account & Authentication presentation contract',
        'compact posture summary',
        'simple tab contract as General Settings',
        'Last Verified Sign-In',
        'Avoid hand-built status badges',
    ):
        require(required in readme, f'Settings README final-lock contract missing: {required}', errors)
    require(
        'verify_settings_final_lock.py' in quality_gate,
        'Settings Final Lock verifier is not release-gated',
        errors,
    )

    if errors:
        print('FAIL — KAORI Settings Final Lock v1')
        for error in errors:
            print(f'- {error}')
        return 1

    print(f'PASS — KAORI Settings Final Lock v1 · {len(templates)} templates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
