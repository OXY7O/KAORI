from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.intelligence.alert_intelligence.recommendation_source import promote_recommendation_to_alert
from app.intelligence.recommendation_alerting import upsert_recommendation_alert_policy
from app.intelligence.service import get_recommendation_finding
from app.models.alert_ops import AlertCase, RecommendationAlertPolicy
from app.models.audit import AuditEvent


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
