from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.identity_provider.catalog import (
    AuthProviderFamily,
    configurable_provider_definitions,
    provider_definition,
)
from app.access.authentication.identity_provider.configuration import (
    IdentityProviderConfiguration,
    apply_identity_provider_configuration,
    identity_provider_configuration_complete,
)
from app.access.rbac.policy import is_local_break_glass, role_is_access_admin_level, role_is_delegable_by_actor
from app.access.rbac.service import assignable_roles_for_actor
from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window, normalize_per_page, positive_int
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider, Role, User

PROVIDER_STATE_OPTIONS = ('all', 'enabled', 'disabled')


def provider_filter_options() -> list[dict[str, str]]:
    return [
        {'value': definition.provider_key, 'label': definition.label}
        for definition in configurable_provider_definitions()
    ]


def normalize_provider_filters(args: Mapping[str, str | None]) -> dict[str, Any]:
    provider_key = (args.get('provider_key') or 'all').strip().lower()
    allowed_provider_keys = {item['value'] for item in provider_filter_options()}
    state = (args.get('state') or 'all').strip().lower()
    return {
        'search': (args.get('search') or '').strip(),
        'provider_key': provider_key if provider_key in allowed_provider_keys else 'all',
        'state': state if state in PROVIDER_STATE_OPTIONS else 'all',
        'page': positive_int(args.get('page'), 1),
        'per_page': normalize_per_page(args.get('per_page')),
    }


def present_identity_provider(provider: IdentityProvider, *, identity_links: int) -> dict[str, Any]:
    definition = provider_definition(provider.provider_key)
    complete = identity_provider_configuration_complete(provider)
    config = provider.configuration_json or {}

    if definition.family == AuthProviderFamily.DIRECTORY:
        access_model = {
            'label': 'Administrative Projection',
            'description': 'Directory identities are projected into KAORI before authentication.',
        }
        credential_reference = str(config.get('bind_password_env') or 'Not Configured')
        connection = str(config.get('server_uri') or 'Not Configured')
        projection = 'Directory Provisioning'
    elif provider.jit_enabled:
        access_model = {
            'label': 'Controlled JIT',
            'description': 'Approved external identities may create a KAORI account with the configured default role.',
        }
        credential_reference = str(config.get('client_secret_env') or 'Not Configured')
        connection = 'External Browser Authentication Application'
        projection = 'Controlled JIT'
    else:
        access_model = {
            'label': 'Pre-Provisioned SSO',
            'description': 'Only external identities already linked to a KAORI account may authenticate.',
        }
        credential_reference = str(config.get('client_secret_env') or 'Not Configured')
        connection = 'External Browser Authentication Application'
        projection = 'Pre-Provisioned'

    return {
        'record': provider,
        'definition': definition,
        'type': {
            'label': definition.label,
            'short_label': definition.short_label,
            'icon': definition.icon,
        },
        'configuration': {
            'label': 'Configured' if complete else 'Incomplete',
            'tone': 'normal' if complete else 'warning',
            'icon': 'circle-check' if complete else 'triangle-alert',
            'complete': complete,
        },
        'state': {
            'label': 'Enabled' if provider.enabled else 'Disabled',
            'tone': 'normal' if provider.enabled else 'unknown',
            'icon': 'power' if provider.enabled else 'power-off',
        },
        'identity_links': int(identity_links or 0),
        'access_model': access_model,
        'credential_reference': credential_reference,
        'connection': connection,
        'projection': projection,
        'validation': {
            'label': 'On Demand',
            'description': 'Validation runs live and is not stored as durable provider readiness evidence.',
        },
    }


def _provider_link_counts() -> dict[int, int]:
    rows = (
        db.session.query(ExternalIdentityLink.provider_id, func.count(ExternalIdentityLink.id))
        .group_by(ExternalIdentityLink.provider_id)
        .all()
    )
    return {int(provider_id): int(count or 0) for provider_id, count in rows}


def _matches_provider_row(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    search = str(filters['search'] or '').lower()
    record = row['record']
    if search:
        haystack = ' '.join(
            (record.display_name or '', record.key or '', row['type']['label'], row['access_model']['label'])
        ).lower()
        if search not in haystack:
            return False
    if filters['provider_key'] != 'all' and record.provider_key != filters['provider_key']:
        return False
    if filters['state'] == 'enabled' and not record.enabled:
        return False
    if filters['state'] == 'disabled' and record.enabled:
        return False
    return True


def _provider_summary(
    providers: list[IdentityProvider],
    presentations: list[dict[str, Any]],
    link_counts: dict[int, int],
    *,
    matching_count: int,
) -> dict[str, Any]:
    configured_count = sum(1 for row in presentations if row['configuration']['complete'])
    enabled_count = sum(1 for provider in providers if provider.enabled)
    directory_provider_ids = {
        provider.id
        for provider in providers
        if provider_definition(provider.provider_key).family == AuthProviderFamily.DIRECTORY
    }
    directory_count = len(directory_provider_ids)
    sso_count = sum(
        1 for provider in providers if provider_definition(provider.provider_key).family == AuthProviderFamily.SSO
    )
    review_count = sum(
        1
        for provider, row in zip(providers, presentations, strict=True)
        if provider.enabled and not row['configuration']['complete']
    )
    posture_label, posture_tone = _provider_posture(
        total=len(providers),
        configured=configured_count,
        enabled=enabled_count,
        review=review_count,
    )
    return {
        'total': len(providers),
        'configured': configured_count,
        'enabled': enabled_count,
        'directory': directory_count,
        'sso': sso_count,
        'identity_links': sum(link_counts.values()),
        'directory_identity_links': sum(
            count for provider_id, count in link_counts.items() if provider_id in directory_provider_ids
        ),
        'matching': matching_count,
        'review': review_count,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
    }


def _provider_posture(*, total: int, configured: int, enabled: int, review: int) -> tuple[str, str]:
    if total <= 0:
        return 'Not Configured', 'unknown'
    if review > 0:
        return 'Review Required', 'warning'
    if enabled > 0:
        return 'Enabled', 'normal'
    if configured == total:
        return 'Configured', 'info'
    return 'Drafts', 'unknown'


def build_identity_provider_payload(filters: dict[str, Any]) -> dict[str, Any]:
    providers = IdentityProvider.query.order_by(
        IdentityProvider.provider_key.asc(), IdentityProvider.display_name.asc()
    ).all()
    link_counts = _provider_link_counts()
    presentations = [
        present_identity_provider(provider, identity_links=link_counts.get(provider.id, 0)) for provider in providers
    ]
    matching_rows = [row for row in presentations if _matches_provider_row(row, filters)]
    matching_count = len(matching_rows)
    pagination = build_pagination_window(total_items=matching_count, page=filters['page'], per_page=filters['per_page'])
    provider_rows = matching_rows[pagination.offset : pagination.offset + pagination.per_page]
    return {
        'provider_rows': provider_rows,
        'summary': _provider_summary(providers, presentations, link_counts, matching_count=matching_count),
        'filters': {**filters, 'page': pagination.page, 'per_page': pagination.per_page},
        'pagination': pagination.as_dict(),
        'per_page_options': list(PER_PAGE_OPTIONS),
        'pagination_query': {
            'tab': 'providers',
            'per_page': pagination.per_page,
            'search': filters['search'],
            'provider_key': filters['provider_key'],
            'state': filters['state'],
        },
        'provider_filter_options': provider_filter_options(),
        'provider_state_options': list(PROVIDER_STATE_OPTIONS),
    }


def assign_provider_role_choices(form, *, actor: User) -> None:
    roles = assignable_roles_for_actor(actor)
    form.default_role_id.choices = [(0, 'Select role'), *((role.id, role.display_name) for role in roles)]


def provider_default_role_assignment_error(actor: User, role_id: int | None) -> str | None:
    if not role_id:
        return None
    role = db.session.get(Role, role_id)
    if role is None or not role.is_active:
        return 'The selected JIT default role is unavailable.'
    if role_is_delegable_by_actor(actor, role):
        return None
    if role_is_access_admin_level(role) and not is_local_break_glass(actor):
        return 'Only a Local Database Super Admin can assign an administrator-level JIT default role.'
    return 'The selected JIT default role exceeds your delegation boundary.'


def create_identity_provider(configuration: IdentityProviderConfiguration) -> IdentityProvider:
    provider = IdentityProvider()
    apply_identity_provider_configuration(provider, configuration)
    db.session.add(provider)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return provider


def update_identity_provider(
    provider: IdentityProvider,
    configuration: IdentityProviderConfiguration,
) -> IdentityProvider:
    apply_identity_provider_configuration(provider, configuration)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return provider


def commit_identity_projection() -> None:
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def rollback_identity_provider_transaction() -> None:
    db.session.rollback()
