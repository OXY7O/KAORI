from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, func

from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider, User
from app.users.service import present_identity_provider


def build_identity_provider_summary() -> dict[str, Any]:
    """Return provider posture without building registry rows or pagination."""

    providers = IdentityProvider.query.order_by(
        IdentityProvider.provider_type.asc(), IdentityProvider.display_name.asc()
    ).all()
    presentations = [present_identity_provider(provider, identity_links=0) for provider in providers]
    configured = sum(1 for row in presentations if row['configuration']['complete'])
    enabled = sum(1 for provider in providers if provider.enabled)
    enabled_incomplete = sum(
        1
        for provider, row in zip(providers, presentations, strict=True)
        if provider.enabled and not row['configuration']['complete']
    )
    jit_policy_review = 0
    for provider in providers:
        if not provider.enabled or not provider.jit_enabled:
            continue
        role = provider.default_role
        policy_ready = bool(role and role.is_active and role.name != 'admin')
        if provider.provider_type == 'google_oidc':
            policy_ready = policy_ready and bool(provider.allowed_domains_list)
        elif provider.provider_type == 'github_oauth':
            policy_ready = policy_ready and bool(provider.allowed_subjects_list)
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
    """Return access-control posture for the managed user population."""

    population = (
        db.session.query(
            func.count(User.id).label('total'),
            func.sum(case((User.account_is_active.is_(True), 1), else_=0)).label('active'),
            func.sum(case((User.account_is_active.is_(False), 1), else_=0)).label('inactive'),
            func.sum(
                case(
                    (
                        and_(
                            User.is_super_admin.is_(True),
                            User.account_is_active.is_(True),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label('active_super_admins'),
            func.sum(
                case(
                    (
                        and_(
                            User.account_is_active.is_(True),
                            User.is_super_admin.is_(False),
                            User.role_id.is_(None),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label('unassigned_active_users'),
        )
        .filter(User.deleted_at.is_(None))
        .one()
    )
    external_users = User.query.filter(
        User.deleted_at.is_(None),
        User.auth_source != 'database',
    ).count()

    total = int(population.total or 0)
    active = int(population.active or 0)
    inactive = int(population.inactive or 0)
    active_super_admins = int(population.active_super_admins or 0)
    unassigned_active_users = int(population.unassigned_active_users or 0)
    review_count = int(active == 0) + int(active_super_admins == 0) + int(unassigned_active_users > 0)

    return {
        'total': total,
        'active': active,
        'inactive': inactive,
        'external': int(external_users or 0),
        'active_super_admins': active_super_admins,
        'unassigned_active_users': unassigned_active_users,
        'review_count': review_count,
        'posture_label': 'Review Required' if review_count else 'Ready',
        'posture_tone': 'warning' if review_count else 'normal',
    }
