from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.intelligence.alert_intelligence.recommendation_source import (
    apply_rule_exception_to_active_findings,
    promote_recommendation_to_alert,
)
from app.intelligence.catalog import risk_exception_policy
from app.intelligence.recommendation_alerting import (
    base_rule_key,
    catalog_rule,
    upsert_recommendation_alert_policy,
)
from app.intelligence.rule_exceptions import (
    RuleExceptionCreateSpec,
    create_rule_exception,
    finding_asset_key,
    revoke_rule_exception,
)
from app.intelligence.service import get_active_recommendation_findings, get_recommendation_finding
from app.models.alert_ops import (
    AlertCase,
    RecommendationAlertPolicy,
    RecommendationAlertState,
    RuleException,
)
from app.models.audit import AuditEvent
from app.models.user import User


def promote_recommendation_command(
    recommendation_key: str,
    *,
    actor_user_id: int | None,
) -> AlertCase:
    finding = get_recommendation_finding(recommendation_key)
    if finding is None:
        raise ValueError('The recommendation is no longer active in committed evidence.')
    try:
        case = promote_recommendation_to_alert(finding, actor_user_id=actor_user_id)
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return case


def save_recommendation_alert_policy_command(
    *,
    rule_key: str,
    eligible: bool,
    mode: str,
    stability_window_minutes: int,
    minimum_occurrences: int,
    grouping_mode: str,
    actor_user_id: int | None,
) -> RecommendationAlertPolicy:
    try:
        row = upsert_recommendation_alert_policy(
            rule_key=rule_key,
            eligible=eligible,
            mode=mode,
            stability_window_minutes=stability_window_minutes,
            minimum_occurrences=minimum_occurrences,
            grouping_mode=grouping_mode,
            actor_user_id=actor_user_id,
        )
        db.session.flush()
        audit = AuditEvent()
        audit.actor_user_id = actor_user_id
        audit.target_type = 'intelligence_rule'
        audit.target_id = rule_key
        audit.action = 'recommendation_alert_policy_updated'
        audit.summary = 'Recommendation alert escalation policy updated.'
        audit.metadata_json = {
            'module': 'Intelligence',
            'rule_key': rule_key,
            'eligible': row.eligible,
            'mode': row.mode,
            'stability_window_minutes': row.stability_window_minutes,
            'minimum_occurrences': row.minimum_occurrences,
            'grouping_mode': row.grouping_mode,
        }
        db.session.add(audit)
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return row


@dataclass(frozen=True, slots=True)
class CreateRuleExceptionCommand:
    rule_key: str
    asset_key: str
    scope_mode: str
    finding_keys: tuple[str, ...]
    reason: str
    risk_reference: str | None
    expires_in_days: int
    actor_user_id: int | None
    owner_user_id: int | None = None


def _covered_rule_findings(
    command: CreateRuleExceptionCommand,
    *,
    allowed_scopes: set[str],
) -> tuple[str, str, set[str], list[dict[str, object]]]:
    normalized_asset = str(command.asset_key or '').strip()
    if not normalized_asset:
        raise ValueError('Select the asset covered by this accepted-risk exception.')
    rule_findings = [
        finding
        for finding in get_active_recommendation_findings()
        if base_rule_key(str(finding.get('rule_key') or '')) == command.rule_key
        and finding_asset_key(finding) == normalized_asset
    ]
    if not rule_findings:
        raise ValueError('No active findings for this rule are currently attached to the selected asset.')

    normalized_scope = str(command.scope_mode or '').strip().lower()
    if normalized_scope not in allowed_scopes:
        raise ValueError('The selected accepted-risk scope is not allowed by this Rule Catalog definition.')
    selected_keys = {str(value or '').strip() for value in command.finding_keys if str(value or '').strip()}
    if normalized_scope == 'rule_asset':
        return normalized_asset, normalized_scope, set(), list(rule_findings)
    if normalized_scope != 'finding_keys':
        raise ValueError('Exception scope must be Entire Asset or Selected Findings.')
    if not selected_keys:
        raise ValueError('Select at least one active finding for the exception.')
    active_keys = {str(finding.get('rule_key') or '') for finding in rule_findings}
    if selected_keys - active_keys:
        raise ValueError('One or more selected findings no longer belong to the selected active asset scope.')
    covered = [finding for finding in rule_findings if str(finding.get('rule_key') or '') in selected_keys]
    return normalized_asset, normalized_scope, selected_keys, covered


def _resolve_owner_user_id(command: CreateRuleExceptionCommand) -> int | None:
    owner_user_id = command.owner_user_id if command.owner_user_id is not None else command.actor_user_id
    if owner_user_id is None:
        return None
    owner = User.query.filter_by(id=owner_user_id).first()
    if owner is None or not owner.is_active:
        raise ValueError('Select an active user as the accepted-risk owner.')
    return owner_user_id


def create_rule_exception_command(
    command: CreateRuleExceptionCommand,
) -> tuple[RuleException, dict[str, int]]:
    rule = catalog_rule(command.rule_key)
    if rule is None:
        raise ValueError('The selected Intelligence rule does not exist.')
    if str(rule.get('status') or '') != 'available':
        raise ValueError('Accepted risk can only be recorded for an available KAORI rule.')
    exception_policy = risk_exception_policy(command.rule_key)
    if not bool(exception_policy.get('enabled')):
        raise ValueError('Accepted risk is not enabled for this Rule Catalog definition.')

    raw_allowed_scopes = exception_policy.get('allowed_scope_modes')
    allowed_scope_values = raw_allowed_scopes if isinstance(raw_allowed_scopes, list) else []
    allowed_scopes = {str(value) for value in allowed_scope_values}
    normalized_asset, normalized_scope, selected_keys, covered_findings = _covered_rule_findings(
        command,
        allowed_scopes=allowed_scopes,
    )
    owner_user_id = _resolve_owner_user_id(command)
    days = max(1, min(int(command.expires_in_days or 0), 3650))
    now = datetime.now(UTC)
    try:
        row = create_rule_exception(
            RuleExceptionCreateSpec(
                rule_key=command.rule_key,
                domain=str(rule.get('domain') or ''),
                asset_key=normalized_asset,
                scope_mode=normalized_scope,
                finding_keys=tuple(sorted(selected_keys)),
                reason=command.reason,
                risk_reference=command.risk_reference,
                expires_at=now + timedelta(days=days),
            ),
            actor_user_id=command.actor_user_id,
            owner_user_id=owner_user_id,
            now=now,
        )
        db.session.flush()
        stats = apply_rule_exception_to_active_findings(row, covered_findings, now=now)
        audit = AuditEvent()
        audit.actor_user_id = command.actor_user_id
        audit.target_type = 'rule_exception'
        audit.target_id = row.public_id
        audit.action = 'rule_exception_created'
        audit.summary = 'Time-bounded accepted-risk exception created for an Intelligence rule.'
        audit.metadata_json = {
            'module': 'Intelligence',
            'rule_key': row.rule_key,
            'asset_key': row.asset_key,
            'scope_mode': row.scope_mode,
            'covered_findings': stats['covered'],
            'cases_closed': stats['cases_closed'],
            'risk_reference': row.risk_reference,
            'owner_user_id': row.owner_user_id,
            'expires_at': row.expires_at.isoformat(),
        }
        db.session.add(audit)
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return row, stats


def revoke_rule_exception_command(
    exception_public_id: str,
    *,
    reason: str,
    actor_user_id: int | None,
) -> tuple[RuleException, int]:
    row = RuleException.query.filter_by(public_id=exception_public_id).first()
    if row is None:
        raise ValueError('The accepted-risk exception no longer exists.')
    try:
        revoke_rule_exception(row, reason=reason, actor_user_id=actor_user_id)
        states = RecommendationAlertState.query.filter_by(rule_exception_id=row.id, active=True).all()
        released = len(states)
        for state in states:
            state.rule_exception_id = None
        audit = AuditEvent()
        audit.actor_user_id = actor_user_id
        audit.target_type = 'rule_exception'
        audit.target_id = row.public_id
        audit.action = 'rule_exception_revoked'
        audit.summary = 'Accepted-risk exception revoked; active findings return to normal alert eligibility.'
        audit.metadata_json = {
            'module': 'Intelligence',
            'rule_key': row.rule_key,
            'asset_key': row.asset_key,
            'released_findings': released,
            'reason': str(reason or '').strip()[:500],
        }
        db.session.add(audit)
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return row, released
