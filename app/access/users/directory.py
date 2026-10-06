from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_

from app.access.authentication.identity_provider.catalog import (
    AuthProviderFamily,
    provider_definition,
    provider_keys_for_family,
)
from app.access.users.access_summary import build_user_access_summary
from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window, normalize_per_page, positive_int
from app.extensions.db import db
from app.models import Role, User

USER_STATUS_OPTIONS = ['all', 'active', 'inactive', 'deleted']
USER_AUTH_SOURCE_OPTIONS = ['all', 'database', 'directory', 'sso']


def normalize_user_filters(args: Mapping[str, str | None]) -> dict[str, Any]:
    status = (args.get('status') or 'all').strip().lower()
    auth_source = (args.get('auth_source') or 'all').strip().lower()
    role_id_raw = (args.get('role_id') or 'all').strip()

    return {
        'search': (args.get('search') or '').strip(),
        'status': status if status in USER_STATUS_OPTIONS else 'all',
        'auth_source': auth_source if auth_source in USER_AUTH_SOURCE_OPTIONS else 'all',
        'role_id': int(role_id_raw) if role_id_raw.isdigit() else None,
        'page': positive_int(args.get('page'), 1),
        'per_page': normalize_per_page(args.get('per_page')),
    }


def _auth_source_presentation(auth_source: str) -> dict[str, str]:
    normalized = str(auth_source or '').strip().lower()
    try:
        definition = provider_definition(normalized)
    except ValueError:
        return {'label': 'Unknown Identity Source', 'icon': 'key-round', 'family': 'unknown'}

    icons = {
        AuthProviderFamily.DATABASE: 'database',
        AuthProviderFamily.DIRECTORY: 'building-2',
        AuthProviderFamily.SSO: 'fingerprint',
    }
    return {
        'label': definition.label,
        'icon': icons.get(definition.family, 'key-round'),
        'family': definition.family.value,
    }


def build_user_identity_context(user: User) -> dict[str, Any]:
    matching_link = next(
        (
            link
            for link in user.external_identities
            if link.provider is not None and link.provider.provider_key == user.auth_source
        ),
        None,
    )
    identity_provider = matching_link.provider if matching_link is not None else None
    source = _auth_source_presentation(user.auth_source)

    if user.auth_source == 'database':
        credential_owner = 'KAORI'
        credential_detail = 'KAORI stores the password hash and owns the password reset workflow.'
    elif source['family'] == AuthProviderFamily.DIRECTORY.value:
        credential_owner = identity_provider.display_name if identity_provider is not None else 'LDAP directory'
        credential_detail = (
            'The directory validates the password; KAORI stores only the linked identity and access controls.'
        )
    elif source['family'] == AuthProviderFamily.SSO.value:
        credential_owner = identity_provider.display_name if identity_provider is not None else source['label']
        credential_detail = (
            'The external provider authenticates the user; KAORI enforces the identity link, lifecycle, and RBAC role.'
        )
    else:
        credential_owner = 'External provider'
        credential_detail = 'The external provider owns authentication; KAORI manages lifecycle and authorization.'

    projection_type = str(matching_link.projection_type) if matching_link is not None else ''
    projection_labels = {
        'administrative': 'Administrative provisioning',
        'jit': 'Controlled JIT provisioning',
    }
    projection_label = projection_labels.get(projection_type) or (
        'Local account' if user.auth_source == 'database' else 'Identity link unavailable'
    )

    if user.auth_source == 'database':
        identity_state = 'Local'
        identity_tone = 'normal'
        identity_reason = 'Local Database is the authoritative identity source.'
    elif matching_link is None:
        identity_state = 'Link Missing'
        identity_tone = 'warning'
        identity_reason = 'No external identity link matches the configured authentication source.'
    elif identity_provider is None:
        identity_state = 'Provider Missing'
        identity_tone = 'warning'
        identity_reason = 'The external identity link no longer resolves to an identity provider.'
    elif not identity_provider.enabled:
        identity_state = 'Provider Disabled'
        identity_tone = 'warning'
        identity_reason = f'{identity_provider.display_name} is disabled.'
    else:
        identity_state = 'Ready'
        identity_tone = 'normal'
        identity_reason = f'{identity_provider.display_name} is enabled and the external identity link is present.'

    return {
        'type_label': source['label'],
        'source_family': source['family'],
        'icon': source['icon'],
        'credential_owner': credential_owner,
        'credential_detail': credential_detail,
        'provider_name': identity_provider.display_name if identity_provider is not None else source['label'],
        'provider_key': identity_provider.key if identity_provider is not None else None,
        'provider_enabled': bool(identity_provider.enabled)
        if identity_provider is not None
        else user.auth_source == 'database',
        'projection_label': projection_label,
        'external_username': matching_link.external_username if matching_link is not None else None,
        'subject': matching_link.subject if matching_link is not None else user.external_id,
        'distinguished_name': matching_link.distinguished_name if matching_link is not None else None,
        'identity_state': identity_state,
        'identity_tone': identity_tone,
        'identity_reason': identity_reason,
        'link_present': matching_link is not None,
    }


def present_user_record(user: User, *, identity_context: dict[str, Any]) -> dict[str, Any]:
    if user.deleted_at is not None:
        lifecycle = {'label': 'Deleted', 'tone': 'unknown', 'icon': 'archive'}
    elif user.account_is_active:
        lifecycle = {'label': 'Active', 'tone': 'normal', 'icon': 'circle-check'}
    else:
        lifecycle = {'label': 'Inactive', 'tone': 'unknown', 'icon': 'pause-circle'}

    source = _auth_source_presentation(user.auth_source)

    if user.role_record is None:
        role = {
            'label': 'Unassigned',
            'state_label': 'Unassigned',
            'state_tone': 'warning',
            'state_icon': 'circle-slash-2',
        }
    else:
        role_active = bool(user.role_record.is_active)
        role = {
            'label': user.role_record.display_name,
            'state_label': 'Active' if role_active else 'Inactive',
            'state_tone': 'normal' if role_active else 'warning',
            'state_icon': 'badge-check' if role_active else 'triangle-alert',
        }

    if user.deleted_at is not None:
        access = {
            'label': 'Restricted',
            'tone': 'unknown',
            'icon': 'archive',
            'reason': 'The account is soft deleted.',
        }
    elif not user.account_is_active:
        access = {
            'label': 'Restricted',
            'tone': 'unknown',
            'icon': 'pause-circle',
            'reason': 'The account lifecycle is inactive.',
        }
    elif user.is_super_admin:
        if user.auth_source == 'database':
            access = {
                'label': 'Break-glass',
                'tone': 'maintenance',
                'icon': 'shield-check',
                'reason': 'Local Database Super Admin authority is active.',
            }
        else:
            access = {
                'label': 'Blocked',
                'tone': 'warning',
                'icon': 'shield-alert',
                'reason': 'Super Admin authority is valid only for Local Database break-glass accounts.',
            }
    elif user.role_record is None:
        access = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'circle-slash-2',
            'reason': 'No active RBAC role is assigned.',
        }
    elif not user.role_record.is_active:
        access = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'reason': 'The assigned RBAC role is inactive.',
        }
    elif user.auth_source != 'database' and identity_context['identity_state'] != 'Ready':
        access = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'fingerprint',
            'reason': identity_context['identity_reason'],
        }
    else:
        access = {
            'label': 'Allowed',
            'tone': 'normal',
            'icon': 'shield-check',
            'reason': 'Account lifecycle, identity source, and RBAC admission are ready.',
        }

    return {'lifecycle': lifecycle, 'source': source, 'role': role, 'access': access}


def build_users_payload(filters: dict[str, Any], actor: User | None = None) -> dict[str, Any]:
    query = User.query

    if filters['status'] != 'deleted':
        query = query.filter(User.deleted_at.is_(None))

    if filters['status'] == 'active':
        query = query.filter(User.account_is_active.is_(True), User.deleted_at.is_(None))
    elif filters['status'] == 'inactive':
        query = query.filter(User.account_is_active.is_(False), User.deleted_at.is_(None))
    elif filters['status'] == 'deleted':
        query = query.filter(User.deleted_at.is_not(None))

    if filters['auth_source'] != 'all':
        source_values = provider_keys_for_family(filters['auth_source'])
        query = query.filter(User.auth_source.in_(source_values))

    if filters['role_id']:
        query = query.filter(User.role_id == filters['role_id'])

    if filters['search']:
        search_term = f'%{filters["search"]}%'
        query = query.filter(
            or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term),
                User.display_name.ilike(search_term),
            )
        )

    total_items = query.count()
    pagination = build_pagination_window(
        total_items=total_items,
        page=filters['page'],
        per_page=filters['per_page'],
    )

    users = (
        query.order_by(User.deleted_at.asc(), User.account_is_active.desc(), User.username.asc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
        .all()
    )

    source_count_rows = (
        db.session.query(User.auth_source, func.count(User.id))
        .filter(User.deleted_at.is_(None))
        .group_by(User.auth_source)
        .all()
    )
    source_counts = {str(source): int(count or 0) for source, count in source_count_rows if source is not None}
    local_users = int(source_counts.get('database', 0))
    directory_users = sum(
        count
        for source, count in source_counts.items()
        if source in provider_keys_for_family(AuthProviderFamily.DIRECTORY)
    )
    sso_users = sum(
        count for source, count in source_counts.items() if source in provider_keys_for_family(AuthProviderFamily.SSO)
    )
    external_users = sum(count for source, count in source_counts.items() if source != 'database')
    deleted_users = User.query.filter(User.deleted_at.is_not(None)).count()
    roles = Role.query.order_by(Role.is_active.desc(), Role.display_name.asc()).all()

    identity_contexts = {user.id: build_user_identity_context(user) for user in users}
    user_presentations = {
        user.id: present_user_record(user, identity_context=identity_contexts[user.id]) for user in users
    }
    access_summary = build_user_access_summary()
    identity_source_count = sum(
        1
        for family in (AuthProviderFamily.DATABASE, AuthProviderFamily.DIRECTORY, AuthProviderFamily.SSO)
        if sum(source_counts.get(item, 0) for item in provider_keys_for_family(family)) > 0
    )
    can_manage_users = bool(actor and actor.has_permission('users.manage'))

    summary = {
        **access_summary,
        'managed': int(access_summary['total']) + int(deleted_users or 0),
        'deleted': int(deleted_users or 0),
        'local': local_users,
        'directory': int(directory_users),
        'sso': int(sso_users),
        'external': int(external_users),
        'identity_source_count': identity_source_count,
    }

    from app.access.users.service import build_user_action_policies

    return {
        'users': users,
        'roles': roles,
        'summary': summary,
        'filters': {**filters, 'page': pagination.page, 'per_page': pagination.per_page},
        'pagination': pagination.as_dict(),
        'per_page_options': list(PER_PAGE_OPTIONS),
        'status_options': USER_STATUS_OPTIONS,
        'auth_source_options': USER_AUTH_SOURCE_OPTIONS,
        'user_actions': build_user_action_policies(actor, users),
        'user_presentations': user_presentations,
        'user_identity_contexts': identity_contexts,
        'can_manage_users': can_manage_users,
        'pagination_query': {
            'per_page': pagination.per_page,
            'search': filters['search'],
            'status': filters['status'],
            'auth_source': filters['auth_source'],
            'role_id': filters['role_id'] or 'all',
        },
    }
