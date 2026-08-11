#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCK_DOCS = (
    'docs/architecture/ACCESS_OWNERSHIP.md',
    'docs/design/KAORI_ACCESS_LOCK_V1.md',
    'docs/design/audits/KAORI_ACCESS_FINAL_LOCK_AUDIT_2026_08_11.md',
)

ACTIVITY_TEMPLATES = (
    'app/templates/notifications/activity.html',
    'app/templates/notifications/components/_activity_center_items.html',
    'app/templates/notifications/partials/_activity_detail.html',
    'app/templates/notifications/partials/_activity_summary_cards.html',
    'app/templates/notifications/partials/_activity_table_card.html',
    'app/templates/notifications/partials/_activity_table_content.html',
)

RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border|ring|shadow|fill|stroke)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|purple|violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
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


def access_templates() -> list[Path]:
    paths = list((ROOT / 'app/templates/access').rglob('*.html'))
    paths.extend((ROOT / 'app/templates/users').rglob('*.html'))
    paths.extend(ROOT / relative for relative in ACTIVITY_TEMPLATES)
    return sorted(set(paths))


def main() -> int:
    errors: list[str] = []

    for relative in LOCK_DOCS:
        require((ROOT / relative).exists(), f'missing Access lock artifact: {relative}', errors)

    templates = access_templates()
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

    ownership = read('scripts/verify_access_ownership.py')
    access_readme = read('app/access/README.md')
    ownership_doc = read('docs/architecture/ACCESS_OWNERSHIP.md')
    lock_doc = read('docs/design/KAORI_ACCESS_LOCK_V1.md')
    quality_gate = read('scripts/quality_gate.sh')

    for required in (
        'Access v1 is final-locked',
        'scripts/verify_access_final_lock.py',
    ):
        require(required in access_readme, f'Access README final-lock contract missing: {required}', errors)
    require('Status: **Final Locked — Access v1**' in ownership_doc, 'Access ownership status is not final locked', errors)
    require('Status: **FINAL LOCKED**' in lock_doc, 'Access lock document is not marked FINAL LOCKED', errors)
    require('verify_access_final_lock.py' in quality_gate, 'Access Final Lock verifier is not release-gated', errors)
    require('PASS — KAORI Access Ownership v1.1' in ownership, 'Access ownership verifier output is not canonical', errors)

    # Access overview is read-only and permission scoped.
    overview_routes = read('app/access/overview/routes.py')
    overview_template = read('app/templates/access/overview/index.html')
    for permission in ('users.view', 'users.manage', 'roles.view', 'settings.view_operational_activity'):
        require(repr(permission) in overview_routes, f'Access Overview permission missing: {permission}', errors)
    require('@any_permission_required(' in overview_routes, 'Access Overview must use any_permission_required', errors)
    require('page_hero.shell_classes()' in overview_template, 'Access Overview must use shared Hero', errors)
    for forbidden in ('hx-post=', 'type="submit"', '<form'):
        require(forbidden not in overview_template, f'Access Overview must remain read-only: {forbidden}', errors)

    # Roles: read/manage separation, protected defaults, concurrency + stale-write protection.
    roles_routes = read('app/access/roles/routes.py')
    roles_service = read('app/access/roles/service.py')
    roles_form = read('app/templates/access/roles/form.html')
    roles_index = read('app/templates/access/roles/index.html')
    roles_registry = read('app/templates/access/roles/partials/_registry.html')
    for required in (
        "@permission_required('roles.view')",
        "@permission_required('roles.manage')",
        'lock_role_for_mutation(role_id)',
        'This role changed after the page was opened',
        'Default role is protected',
    ):
        require(required in roles_routes, f'Roles security contract missing: {required}', errors)
    for required in ('with_for_update()', 'def role_version_token', 'def role_version_matches'):
        require(required in roles_service, f'Roles concurrency contract missing: {required}', errors)
    for required in ('components/page_hero.html', 'components/resource_detail_modal.html'):
        require(required in roles_index, f'Roles shared UI contract missing: {required}', errors)
    for required in ('components/table.html', 'components/loading_bar.html', 'components/pagination.html'):
        require(required in roles_registry, f'Role Registry shared UI contract missing: {required}', errors)
    require('xl:sticky xl:top-5' in roles_form, 'Role form sticky context rail contract drifted', errors)
    require(not (ROOT / 'app/static/js/role_access_tabs.js').exists(), 'obsolete role_access_tabs.js reintroduced', errors)

    # Permission Catalog is read-only; convergence stays command/deployment owned.
    permission_routes = read('app/access/permissions/routes.py')
    permission_service = read('app/access/permissions/service.py')
    permission_index = read('app/templates/access/permissions/index.html')
    permission_workspace = read('app/templates/access/permissions/partials/_workspace.html')
    for required in ("@permission_required('roles.view')", "@bp.get('/<string:permission_key>/details')"):
        require(required in permission_routes, f'Permission Catalog route contract missing: {required}', errors)
    for forbidden in ('seed_default_rbac', 'db.session.commit', '@bp.post'):
        require(forbidden not in permission_routes, f'Permission Catalog GET boundary must remain read-only: {forbidden}', errors)
    require('DEFAULT_PERMISSIONS' in permission_service, 'Permission Catalog must compare code-owned permissions', errors)
    require('components/resource_detail_modal.html' in permission_index, 'Permission detail must use shared modal', errors)
    require('content_driven=true' in permission_index, 'Permission detail modal must remain content-driven', errors)
    require('components/framed_workspace_tabs.html' in permission_workspace, 'Permission Catalog must use shared framed tabs', errors)

    # User lifecycle and last-super-admin protections.
    users_routes = read('app/users/routes.py')
    users_service = read('app/users/service.py')
    user_model = read('app/models/user.py')
    users_index = read('app/templates/users/index.html')
    users_hero = read('app/templates/users/partials/_hero.html')
    for permission in ('users.view', 'users.manage', 'users.activate', 'users.reset_password', 'users.delete'):
        require(f"@permission_required('{permission}')" in users_routes, f'User permission boundary missing: {permission}', errors)
    for required in (
        'lock_active_super_admin_boundary(user)',
        'def is_last_active_super_admin',
        'The last active super admin cannot be deleted.',
        'with_for_update()',
    ):
        source = users_routes if required == 'lock_active_super_admin_boundary(user)' else users_service
        require(required in source, f'User lifecycle security contract missing: {required}', errors)
    require('auth_session_version' in user_model, 'User auth session generation contract missing', errors)
    require('components/page_hero.html' in users_hero, 'User Management must use shared Hero', errors)
    require('destructive_confirmation_modal.js' in users_index, 'User Management must use shared destructive confirmation runtime', errors)

    # Identity Providers: administration-only, secrets external, live validation on demand.
    provider_index = read('app/templates/users/providers/index.html')
    provider_detail = read('app/templates/users/providers/partials/_provider_detail.html')
    provider_routes = users_routes
    for required in (
        "@bp.route('/providers', methods=['GET'])",
        "@bp.post('/providers/test')",
        "@bp.post('/providers/<int:provider_id>/validate')",
        "@permission_required('users.manage')",
        'validate_identity_provider(candidate)',
        'validate_identity_provider(provider)',
    ):
        require(required in provider_routes, f'Identity Provider route contract missing: {required}', errors)
    require('Provider Registry Overview' in provider_index, 'Identity Provider overview contract missing', errors)
    for forbidden in ('Client Secret Value', 'Bind Password Value', 'Last Validated'):
        require(forbidden not in provider_detail, f'Identity Provider secret/durable-validation leak: {forbidden}', errors)

    # Authentication/session boundary: bounded remember-me and super-admin default deny.
    auth_config = read('app/config/default.py')
    auth_session = read('app/auth/session.py')
    auth_audit = read('app/auth/audit.py')
    for required in (
        'AUTH_REMEMBER_ME_DAYS = _bounded_env_int(',
        "'AUTH_REMEMBER_ME_DAYS',",
        'REMEMBER_COOKIE_DURATION = timedelta(days=AUTH_REMEMBER_ME_DAYS)',
        'AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME = _env_bool(',
    ):
        require(required in auth_config, f'Authentication persistence contract missing: {required}', errors)
    require("current_app.config.get('AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME', False)" in auth_session, 'Super-admin remember-me must be default deny', errors)
    for required in (
        "AUTHENTICATION_AUDIT_SCHEMA = 'authentication.v2'",
        "'target_user_id': user.id if user is not None else None",
        "'actor_user_id': authenticated_actor.id if authenticated_actor is not None else None",
    ):
        require(required in auth_audit, f'Authentication actor/target contract missing: {required}', errors)

    # Activity Audit: read-only permission boundary and actor semantics.
    notification_routes = read('app/notifications/routes.py')
    notification_queries = read('app/notifications/queries.py')
    activity_page = read('app/templates/notifications/activity.html')
    for required in (
        "@permission_required('settings.view_operational_activity')",
        "@notifications_bp.get('/activity')",
        "@notifications_bp.get('/activity/<int:notification_id>/details')",
    ):
        require(required in notification_routes, f'Activity Audit route contract missing: {required}', errors)
    for required in (
        'actor_identity = case(',
        "Notification.event_type == 'authentication'",
        "Notification.status != 'success'",
        'func.count(func.distinct(actor_identity))',
        "Notification.event_type != 'authentication'",
        "Notification.status == 'success'",
    ):
        require(required in notification_queries, f'Activity actor contract missing: {required}', errors)
    require(
        'components/resource_detail_modal.html' in activity_page, 'Activity Audit must use shared detail modal', errors
    )
    require('content_driven=true' in activity_page, 'Activity detail modal must remain content-driven', errors)

    # Shared modal must keep Tailwind arbitrary-value tokens contiguous and formatter-protected.
    modal = read('app/templates/components/resource_detail_modal.html')
    require('h-auto max-h-[calc(100dvh-1rem)]' in modal, 'content-driven modal height token is malformed', errors)
    require('max-h-[calc(100dvh-1rem) ]' not in modal, 'formatter whitespace broke modal Tailwind token', errors)
    modal_djlint_off = modal.find('{# djlint:off #}')
    modal_dialog_open = modal.find('<section id="{{ dialog_id }}"')
    modal_dialog_close = modal.find('</section>', modal_dialog_open)
    modal_djlint_on = modal.find('{# djlint:on #}')
    require(
        0 <= modal_djlint_off < modal_dialog_open < modal_dialog_close < modal_djlint_on,
        'modal formatter boundary must wrap the complete shared dialog section',
        errors,
    )

    if errors:
        print('FAIL — KAORI Access Final Lock v1')
        for error in errors:
            print(f'- {error}')
        return 1

    print(f'PASS — KAORI Access Final Lock v1 · {len(templates)} templates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
