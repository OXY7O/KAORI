"""Exact-instance, read-only Central Alert Intelligence Vault provider case view.

Never enumerates Vault sources, performs provider I/O or mutates AlertCases.
Instance policy is separate from Secret namespace/mount scope.
"""

from __future__ import annotations

from flask import abort, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_instance_case_scope
from app.common.pagination import paginate_sequence
from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_provider_plan import _CASE_KEY_RE, _PROFILE
from app.models.alert_ops import AlertCase
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.platform_operations.notifications.service import stage_operational_activity

_MAX_CASES = 100


def _instance_id() -> int | None:
    raw = request.args.get('instance_id', '')
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal():
        return None
    if not 1 <= len(raw) <= 10 or raw.startswith('0'):
        return None
    number = int(raw)
    return number if number > 0 and str(number) == raw else None


def _admit_read(instance_id: int) -> bool:
    actor_id = getattr(current_user, 'id', None)
    if type(actor_id) is not int:
        return False
    decision = evaluate_exact_vault_instance_case_scope(
        actor_user_id=actor_id, instance_id=instance_id,
    )
    if not decision.allowed:
        db.session.rollback()
        return False
    try:
        # Stage mandatory audit inside the same scope-lock transaction as
        # the ensuing case query. Commit only after source rows qualify.
        # Never include case identity, Vault path, source payload or tokens.
        stage_operational_activity(
            user_id=actor_id,
            event_type='vault_provider_case_read',
            status='info',
            title='Vault AlertCase Scope Read',
            message='An exact approved Vault instance case scope was accessed.',
            metadata={
                'module': 'Alert Intelligence',
                'integration_instance_id': instance_id,
                'permission_key': 'secrets_pki.view',
                'policy_ref': decision.policy_ref,
                'policy_revision': decision.revision,
            },
        )
        return True
    except Exception:
        db.session.rollback()
        return False


def _safe_case(case: AlertCase) -> dict[str, object]:
    return {
        'public_id': case.public_id,
        'title': 'Vault Alertmanager source condition',
        'severity': case.severity if case.severity in {'critical', 'warning', 'info'} else 'unknown',
        'source_state': case.source_state if case.source_state in {'firing', 'unknown', 'resolved'} else 'unknown',
        'workflow_state': case.workflow_state,
        'first_seen_at': case.first_seen_at,
        'last_seen_at': case.last_seen_at,
        'routing': 'Suppressed',
    }


def _case_qualified(case: AlertCase, *, instance_id: int) -> bool:
    metadata = case.evidence_json
    if (
        case.domain != 'secrets_pki' or case.asset_type != 'vault_instance'
        or case.source_type != 'provider_alert'
        or case.asset_key != str(instance_id)
        or case.routing_state != 'suppressed'
        or case.routing_override_reason != 'policy_ineligible'
        or not isinstance(case.case_key, str)
        or _CASE_KEY_RE.fullmatch(case.case_key) is None
        or case.source_ref != case.case_key
        or not isinstance(case.labels_json, dict) or case.labels_json
        or not isinstance(metadata, dict)
        or set(metadata) != {'correlation_profile', 'source_binding_id', 'source_integration_id'}
        or metadata.get('correlation_profile') != _PROFILE
    ):
        return False
    binding_id = metadata['source_binding_id']
    source_id = metadata['source_integration_id']
    if type(binding_id) is not int or type(source_id) is not int:
        return False
    binding = db.session.get(IntegrationBinding, binding_id)
    source = db.session.get(IntegrationInstance, source_id)
    return bool(
        binding is not None
        and source is not None
        and source.integration_type == 'alert_source'
        and source.provider_key == 'alertmanager'
        and binding.integration_instance_id == source_id
        and binding.asset_type == 'vault_instance'
        and binding.asset_key == str(instance_id)
        and binding.validation_profile == 'vault-alerts-v1'
        and binding.selector_json == {
            'matchers': [
                {'label': 'vault_instance', 'operator': '=', 'value': str(instance_id)},
            ],
        }
    )


def _read_cases(*, instance_id: int, page: str) -> dict[str, object]:
    try:
        records = (
            AlertCase.query.filter(
                AlertCase.domain == 'secrets_pki',
                AlertCase.asset_type == 'vault_instance',
                AlertCase.source_type == 'provider_alert',
                AlertCase.asset_key == str(instance_id),
            )
            .order_by(AlertCase.last_seen_at.desc(), AlertCase.id.desc())
            .limit(_MAX_CASES + 1).all()
        )
        if len(records) > _MAX_CASES or any(
            not _case_qualified(case, instance_id=instance_id) for case in records
        ):
            return {'status': 'unavailable', 'rows': [], 'pagination': None}
        rows, pagination = paginate_sequence(
            records, page=page, per_page=5, allowed_per_page=(5,),
        )
        return {
            'status': 'ready',
            'rows': [_safe_case(case) for case in rows],
            'pagination': pagination,
        }
    except (SQLAlchemyError, ValueError, TypeError):
        db.session.rollback()
        return {'status': 'unavailable', 'rows': [], 'pagination': None}


def vault_cases_response() -> ResponseReturnValue:
    instance_id = _instance_id()
    if instance_id is None:
        return render_template(
            'intelligence/vault_provider_cases.html',
            instance_id=None, page_data=None,
        )
    if not _admit_read(instance_id):
        abort(404)
    result = _read_cases(instance_id=instance_id, page=request.args.get('page', '1'))
    if result['status'] != 'ready':
        db.session.rollback()
    else:
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort(404)
    return render_template(
        'intelligence/vault_provider_cases.html',
        instance_id=instance_id, page_data=result,
    )


def vault_case_details_response(public_id: str) -> ResponseReturnValue:
    instance_id = _instance_id()
    if instance_id is None or not _admit_read(instance_id):
        abort(404)
    try:
        row = AlertCase.query.filter(
            AlertCase.public_id == public_id,
            AlertCase.domain == 'secrets_pki',
            AlertCase.asset_type == 'vault_instance',
            AlertCase.source_type == 'provider_alert',
            AlertCase.asset_key == str(instance_id),
        ).first()
        if row is None or not _case_qualified(row, instance_id=instance_id):
            db.session.rollback()
            abort(404)
        db.session.commit()
        return render_template(
            'intelligence/vault_provider_case_details.html',
            case=_safe_case(row), instance_id=instance_id,
        )
    except SQLAlchemyError:
        db.session.rollback()
        abort(404)
