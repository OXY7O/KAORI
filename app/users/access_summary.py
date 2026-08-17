from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, func, select

from app.auth.identity_provider.catalog import provider_definition
from app.auth.identity_provider.configuration import identity_provider_configuration_complete
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider, Role, User


def build_identity_provider_summary() -> dict[str, Any]:
    """Return provider posture without building registry rows or pagination."""

    providers = IdentityProvider.query.order_by(
        IdentityProvider.provider_key.asc(), IdentityProvider.display_name.asc()
    ).all()
    configuration_states = {provider.id: identity_provider_configuration_complete(provider) for provider in providers}
    configured = sum(1 for provider in providers if configuration_states[provider.id])
    enabled = sum(1 for provider in providers if provider.enabled)
    enabled_incomplete = sum(1 for provider in providers if provider.enabled and not configuration_states[provider.id])
    jit_policy_review = 0
    for provider in providers:
        if not provider.enabled or not provider.jit_enabled:
            continue
        role = provider.default_role
        policy_ready = bool(role and role.is_active and role.name != 'admin')
        definition = provider_definition(provider.provider_key)
        if definition.admission_policy in {'verified_email_domain_allowlist', 'subject_allowlist'}:
            policy_ready = policy_ready and bool(provider.admission_values)
        if not policy_ready:
            jit_policy_review += 1

    identity_links = ExternalIdentityLink.query.count()
    review_count = enabled_incomplete + jit_policy_review
    if not providers:
        posture_label, posture_tone = 'Not Configured', 'unknown'
    elif review_count:
        posture_label, posture_tone = 'Review Required', 'warning'
    elif enabled:
        posture_label, posture_tone = 'Enabled', 'normal'
    elif configured == len(providers):
        posture_label, posture_tone = 'Configured', 'info'
    else:
        posture_label, posture_tone = 'Drafts', 'unknown'

    return {
        'total': len(providers),
        'configured': configured,
        'enabled': enabled,
        'identity_links': identity_links,
        'enabled_incomplete': enabled_incomplete,
        'jit_policy_review': jit_policy_review,
        'review_count': review_count,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
    }


def build_user_access_summary() -> dict[str, Any]:
    """Return authoritative access-control posture for the managed user population."""

    population = (
        db.session.query(
            func.count(User.id).label('total'),
            func.sum(case((User.account_is_active.is_(True), 1), else_=0)).label('active'),
            func.sum(case((User.account_is_active.is_(False), 1), else_=0)).label('inactive'),
            func.sum(
                case(
                    (
                        and_(
                            User.auth_source == 'database',
                            User.is_super_admin.is_(True),
                            User.account_is_active.is_(True),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label('active_local_super_admins'),
        )
        .filter(User.deleted_at.is_(None))
        .one()
    )

    unassigned_active_users = User.query.filter(
        User.deleted_at.is_(None),
        User.account_is_active.is_(True),
        User.is_super_admin.is_(False),
        User.role_id.is_(None),
    ).count()
    inactive_role_users = (
        User.query.join(Role, Role.id == User.role_id)
        .filter(
            User.deleted_at.is_(None),
            User.account_is_active.is_(True),
            User.is_super_admin.is_(False),
            Role.is_active.is_(False),
        )
        .count()
    )
    authorization_review = int(unassigned_active_users or 0) + int(inactive_role_users or 0)

    enabled_matching_identity = (
        select(ExternalIdentityLink.id)
        .join(IdentityProvider, IdentityProvider.id == ExternalIdentityLink.provider_id)
        .where(
            ExternalIdentityLink.user_id == User.id,
            IdentityProvider.provider_key == User.auth_source,
            IdentityProvider.enabled.is_(True),
        )
        .exists()
    )
    external_identity_review = User.query.filter(
        User.deleted_at.is_(None),
        User.account_is_active.is_(True),
        User.auth_source != 'database',
        ~enabled_matching_identity,
    ).count()
    invalid_external_super_admins = User.query.filter(
        User.deleted_at.is_(None),
        User.is_super_admin.is_(True),
        User.auth_source != 'database',
    ).count()
    external_users = User.query.filter(
        User.deleted_at.is_(None),
        User.auth_source != 'database',
    ).count()

    total = int(population.total or 0)
    active = int(population.active or 0)
    inactive = int(population.inactive or 0)
    active_super_admins = int(population.active_local_super_admins or 0)
    unassigned_active_users = int(unassigned_active_users or 0)
    inactive_role_users = int(inactive_role_users or 0)
    authorization_review = int(authorization_review or 0)
    external_identity_review = int(external_identity_review or 0)
    invalid_external_super_admins = int(invalid_external_super_admins or 0)
    access_review = authorization_review + external_identity_review + invalid_external_super_admins
    review_count = int(active == 0) + int(active_super_admins == 0) + int(access_review > 0)

    return {
        'total': total,
        'active': active,
        'inactive': inactive,
        'external': int(external_users or 0),
        'active_super_admins': active_super_admins,
        'unassigned_active_users': unassigned_active_users,
        'inactive_role_users': inactive_role_users,
        'authorization_review': authorization_review,
        'external_identity_review': external_identity_review,
        'invalid_external_super_admins': invalid_external_super_admins,
        'access_review': access_review,
        'review_count': review_count,
        'posture_label': 'Review Required' if review_count else 'Ready',
        'posture_tone': 'warning' if review_count else 'normal',
    }
