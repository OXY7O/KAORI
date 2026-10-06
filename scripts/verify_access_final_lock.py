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
    'app/templates/access/activity_audit/index.html',
    'app/templates/access/activity_audit/partials/_activity_detail.html',
    'app/templates/access/activity_audit/partials/_activity_summary_cards.html',
    'app/templates/access/activity_audit/partials/_activity_table_card.html',
    'app/templates/access/activity_audit/partials/_activity_table_content.html',
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
    paths.extend((ROOT / 'app/templates/access/users').rglob('*.html'))
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
    require(
        'Status: **Final Locked — Access v1**' in ownership_doc,
        'Access ownership status is not final locked',
        errors,
    )
    require('Status: **FINAL LOCKED**' in lock_doc, 'Access lock document is not marked FINAL LOCKED', errors)
    require('verify_access_final_lock.py' in quality_gate, 'Access Final Lock verifier is not release-gated', errors)
    require(
        'PASS — KAORI Access Ownership v1.1' in ownership,
        'Access ownership verifier output is not canonical',
        errors,
    )

    # Access overview is read-only and permission scoped.
    overview_routes = read('app/access/overview/routes.py')
    overview_template = read('app/templates/access/overview/index.html')
    for permission in ('users.view', 'users.manage', 'identity_providers.view', 'roles.view', 'activity_audit.view'):
        require(repr(permission) in overview_routes, f'Access Overview permission missing: {permission}', errors)
    require('@any_permission_required(' in overview_routes, 'Access Overview must use any_permission_required', errors)
    require('page_hero.shell_classes()' in overview_template, 'Access Overview must use shared Hero', errors)
    overview_presentation = read('app/access/overview/presentation.py')
    for required in (
        'build_user_access_summary',
        'build_identity_provider_summary',
        'build_roles_index_context',
        'build_permission_registry_snapshot',
        'get_activity_audit_summary',
    ):
        require(
            required in overview_presentation,
            f'Access Overview domain summary contract missing: {required}',
            errors,
        )
    for forbidden in (
        'User.query',
        'IdentityProvider.query',
        'Role.query',
        'Permission.query',
        'Notification.query',
        'db.session',
    ):
        require(
            forbidden not in overview_presentation,
            f'Access Overview must not redefine domain posture with direct persistence access: {forbidden}',
            errors,
        )
    require(
        'table_label.status_indicator_label(boundary.status_label, boundary.status_tone)' in overview_template,
        'Access Overview boundaries must expose authoritative posture',
        errors,
    )
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
        'Protected role cannot be edited',
        'ensure_role_within_delegation_boundary(actor=actor, role=role)',
    ):
        require(required in roles_routes, f'Roles security contract missing: {required}', errors)
    for required in (
        'with_for_update()',
        'def role_version_token',
        'def role_version_matches',
        'def ensure_permission_selection_within_delegation_boundary',
        'def ensure_role_within_delegation_boundary',
        'def validate_custom_role_slug',
        'Confirm the user and Identity Provider impact before deactivating this referenced role.',
    ):
        require(required in roles_service, f'Roles concurrency contract missing: {required}', errors)
    for required in ('components/page_hero.html', 'components/resource_detail_modal.html'):
        require(required in roles_index, f'Roles shared UI contract missing: {required}', errors)
    for required in ('components/table.html', 'components/loading_bar.html', 'components/pagination.html'):
        require(required in roles_registry, f'Role Registry shared UI contract missing: {required}', errors)
    require('xl:sticky xl:top-5' in roles_form, 'Role form sticky context rail contract drifted', errors)
    for required in ('Delegation Boundary', 'Outside Ceiling', 'impact_acknowledged'):
        require(required in roles_form, f'Role form delegation/impact guardrail missing: {required}', errors)
    rbac_defaults = read('app/access/rbac/defaults.py')
    rbac_policy = read('app/access/rbac/policy.py')
    rbac_catalog = read('app/definitions/catalogs/access/rbac/access.yaml')
    for required in ('control_modules:', 'permission_dependencies:', 'access_administration_permissions:'):
        require(required in rbac_catalog, f'RBAC source-controlled policy contract missing: {required}', errors)
    for required in (
        'PERMISSION_MODULE_LABELS',
        'DEFAULT_PERMISSION_DEPENDENCIES',
        'ACCESS_ADMINISTRATION_PERMISSIONS',
    ):
        require(required in rbac_defaults, f'RBAC catalog loader contract missing: {required}', errors)
    for required in ('role_is_access_admin_level', 'role_is_mutation_protected', 'role_slug_is_reserved'):
        require(required in rbac_policy, f'RBAC policy boundary missing: {required}', errors)
    require('Baseline Drift' in roles_index, 'Roles Overview must expose protected-baseline drift', errors)
    require(
        not (ROOT / 'app/static/js/role_access_tabs.js').exists(),
        'obsolete role_access_tabs.js reintroduced',
        errors,
    )

    # Permission Catalog is read-only; convergence stays command/deployment owned.
    permission_routes = read('app/access/permissions/routes.py')
    permission_service = read('app/access/permissions/service.py')
    permission_index = read('app/templates/access/permissions/index.html')
    permission_workspace = read('app/templates/access/permissions/partials/_workspace.html')
    for required in ("@permission_required('roles.view')", "@bp.get('/<string:permission_key>/details')"):
        require(required in permission_routes, f'Permission Catalog route contract missing: {required}', errors)
    for forbidden in ('seed_default_rbac', 'db.session.commit', '@bp.post'):
        require(
            forbidden not in permission_routes,
            f'Permission Catalog GET boundary must remain read-only: {forbidden}',
            errors,
        )
    require(
        'DEFAULT_PERMISSIONS' in permission_service, 'Permission Catalog must compare code-owned permissions', errors
    )
    for required in (
        'DELEGATION_TIER_PRESENTATION',
        'effective_requires',
        'active_user_count',
        'jit_provider_count',
        'database_only_in_use_count',
    ):
        require(required in permission_service, f'Permission Catalog security evidence missing: {required}', errors)
    permission_registry = read('app/templates/access/permissions/partials/_registry.html')
    permission_coverage = read('app/templates/access/permissions/partials/_coverage.html')
    permission_detail = read('app/templates/access/permissions/partials/_permission_detail.html')
    for template in (permission_registry, permission_coverage):
        require('Delegation Boundary' in template, 'Permission Catalog delegation filter missing', errors)
    require('Local Database Super Admin' in permission_detail, 'Permission delegation authority copy missing', errors)
    for required in ('key: integrations.manage', 'key: activity_audit.view'):
        require(required in rbac_catalog, f'Permission ownership key missing: {required}', errors)
    for forbidden in ('key: settings.manage_integrations', 'key: settings.view_operational_activity'):
        require(forbidden not in rbac_catalog, f'Legacy permission ownership key retained: {forbidden}', errors)
    require(
        'components/resource_detail_modal.html' in permission_index, 'Permission detail must use shared modal', errors
    )
    require('content_driven=true' in permission_index, 'Permission detail modal must remain content-driven', errors)
    require(
        'components/framed_workspace_tabs.html' in permission_workspace,
        'Permission Catalog must use shared framed tabs',
        errors,
    )

    # User lifecycle and last-super-admin protections.
    users_routes = read('app/access/users/routes.py')
    users_service = read('app/access/users/service.py')
    users_directory = read('app/access/users/directory.py')
    user_access_summary = read('app/access/users/access_summary.py')
    user_model = read('app/models/user.py')
    user_provisioning_proof = read('app/access/identity_providers/provisioning_proof.py')
    users_index = read('app/templates/access/users/index.html')
    users_hero = read('app/templates/access/users/partials/_hero.html')
    for permission in ('users.view', 'users.manage', 'users.activate', 'users.reset_password', 'users.delete'):
        require(
            f"@permission_required('{permission}')" in users_routes,
            f'User permission boundary missing: {permission}',
            errors,
        )
    for required in (
        'lock_active_super_admin_boundary(user)',
        'def is_last_active_local_super_admin',
        'The last active Local Database super admin cannot be deleted.',
        'with_for_update()',
    ):
        source = users_routes if required == 'lock_active_super_admin_boundary(user)' else users_service
        require(required in source, f'User lifecycle security contract missing: {required}', errors)
    require('auth_session_version' in user_model, 'User auth session generation contract missing', errors)
    require('components/page_hero.html' in users_hero, 'User Management must use shared Hero', errors)
    require(
        'destructive_confirmation_modal.js' in users_index,
        'User Management must use shared destructive confirmation runtime',
        errors,
    )

    for required in (
        "if self.is_super_admin and self.auth_source == 'database':",
        "return 'unassigned'",
    ):
        require(required in user_model, f'User admission model contract missing: {required}', errors)
    for required in (
        "User.auth_source == 'database'",
        'def active_local_super_admin_count()',
        'Super Admin authority is reserved for Local Database break-glass accounts.',
    ):
        require(required in users_service, f'Local break-glass lifecycle contract missing: {required}', errors)
    for required in (
        'def build_users_payload(',
        'def build_user_identity_context(',
        "'label': 'Unassigned'",
        "'label': 'Blocked'",
        "'label': 'Allowed'",
    ):
        require(required in users_directory, f'User effective-access presentation contract missing: {required}', errors)
    require(
        'def build_users_payload(' not in users_service,
        'User directory composition must remain split from mutation service',
        errors,
    )
    for required in (
        "'access_review': access_review",
        "'invalid_external_super_admins': invalid_external_super_admins",
        "'external_identity_review': external_identity_review",
    ):
        require(required in user_access_summary, f'User posture review contract missing: {required}', errors)
    for required in ('URLSafeTimedSerializer', 'verify_projection_proof(', 'PROJECTION_PROOF_MAX_AGE_SECONDS = 600'):
        require(required in user_provisioning_proof, f'LDAP projection proof contract missing: {required}', errors)

    # Identity Providers: provider-neutral administration, adapter-owned protocol behavior, external secrets.
    provider_detail = read('app/templates/access/identity_providers/partials/_provider_detail.html')
    provider_overview = read('app/templates/access/identity_providers/partials/_overview.html')
    provider_routes = read('app/access/identity_providers/routes.py')
    provider_model = read('app/models/identity.py')
    provider_catalog = read('app/access/authentication/identity_provider/catalog.py')
    provider_registry = read('app/access/authentication/identity_provider/registry.py')
    for required in (
        "bp = Blueprint('identity_providers'",
        "url_prefix='/access/identity-providers'",
        "@permission_required('identity_providers.view')",
        "@permission_required('identity_providers.manage')",
        "@permission_required('identity_providers.provision')",
        'validate_identity_provider(candidate)',
        'validate_identity_provider(provider)',
        'get_directory_provider_adapter(selected_provider.adapter_key)',
    ):
        require(required in provider_routes, f'Identity Provider route contract missing: {required}', errors)
    for required in (
        'provider_key:',
        'adapter_key:',
        'configuration_json:',
        'admission_policy_json:',
    ):
        require(required in provider_model, f'Identity Provider canonical model contract missing: {required}', errors)
    for forbidden in ('provider_type:', 'oidc_client_id:', 'server_uri:', 'allowed_domains:', 'allowed_subjects:'):
        require(
            forbidden not in provider_model,
            f'Identity Provider model must not retain product/adapter-specific field: {forbidden}',
            errors,
        )
    require(
        'load_definition_document(' in provider_catalog, 'Identity Provider catalog must be source-controlled', errors
    )
    require(
        "client_secret_placeholder=require_str(raw, 'client_secret_placeholder', path, allow_empty=True)"
        in provider_catalog,
        'Identity Provider catalog must allow non-browser providers to omit a client-secret placeholder',
        errors,
    )
    require(
        "guidance_partial=require_str(raw, 'guidance_partial', path, allow_empty=True)" in provider_catalog,
        'Identity Provider catalog must allow non-configurable providers to omit guidance partials',
        errors,
    )
    require(
        'get_directory_provider_adapter(' in provider_registry, 'Directory adapter registry contract missing', errors
    )
    require('get_browser_sso_adapter(' in provider_registry, 'Browser adapter registry contract missing', errors)
    require('Authentication Source Posture' in provider_overview, 'Identity Provider overview contract missing', errors)
    for tab in ('Overview', 'Providers', 'Directory Provisioning'):
        require(
            tab in read('app/templates/access/identity_providers/partials/_tabs.html'),
            f'Identity Provider tab missing: {tab}',
            errors,
        )
    for forbidden in ('Client Secret Value', 'Bind Password Value', 'Last Validated'):
        require(
            forbidden not in provider_detail, f'Identity Provider secret/durable-validation leak: {forbidden}', errors
        )

    # Authentication/session boundary: bounded remember-me and super-admin default deny.
    auth_config = read('app/config/default.py')
    auth_session = read('app/access/authentication/session.py')
    auth_audit = read('app/access/authentication/audit.py')
    for required in (
        'AUTH_REMEMBER_ME_DAYS = _bounded_env_int(',
        "'AUTH_REMEMBER_ME_DAYS',",
        'REMEMBER_COOKIE_DURATION = timedelta(days=AUTH_REMEMBER_ME_DAYS)',
        'AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME = _env_bool(',
    ):
        require(required in auth_config, f'Authentication persistence contract missing: {required}', errors)
    require(
        "current_app.config.get('AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME', False)" in auth_session,
        'Super-admin remember-me must be default deny',
        errors,
    )
    for required in (
        "AUTHENTICATION_AUDIT_SCHEMA = 'authentication.v2'",
        "'target_user_id': user.id if user is not None else None",
        'actor_snapshot_for_user(authenticated_actor)',
        'unauthenticated_actor_snapshot()',
        'activity.actor_snapshot_json = actor.as_json()',
        'activity.deck_visible = False',
    ):
        require(required in auth_audit, f'Authentication actor/target contract missing: {required}', errors)

    # Activity Audit: Access-owned workspace over the shared Notification evidence store.
    activity_routes = read('app/access/activity_audit/routes.py')
    notification_routes = read('app/platform_operations/notifications/routes.py')
    notification_queries = read('app/platform_operations/notifications/queries.py')
    notification_model = read('app/models/notification.py')
    activity_actors = read('app/platform_operations/notifications/actors.py')
    activity_page = read('app/templates/access/activity_audit/index.html')
    for required in (
        "@permission_required('activity_audit.view')",
        "@bp.get('/')",
        "@bp.get('/<int:notification_id>/details')",
    ):
        require(required in activity_routes, f'Activity Audit route contract missing: {required}', errors)
    require("/activity'" not in notification_routes, 'Notification Center must not own Activity Audit routes', errors)
    for required in (
        'func.count(func.distinct(Notification.actor_key))',
        'Notification.actor_key == normalized_actor_key',
        'Notification.category_key == normalized_category',
        "('all', 'All Hot Records')",
    ):
        require(required in notification_queries, f'Activity evidence-query contract missing: {required}', errors)
    for required in (
        "db.ForeignKey('users.id', ondelete='SET NULL')",
        'actor_snapshot_json',
        'actor_key',
        'category_key',
    ):
        require(required in notification_model, f'Activity evidence model contract missing: {required}', errors)
    for required in (
        "key='system:kaori'",
        "key='unauthenticated'",
        'def resolve_operational_actor(',
    ):
        require(required in activity_actors, f'Activity actor snapshot contract missing: {required}', errors)
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
