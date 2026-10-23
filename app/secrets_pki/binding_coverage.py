"""Bounded Vault Metrics/Alert Source binding posture from committed KAORI records.

HV-06: a validated binding is NOT current Vault API health, observed HA,
successful alert delivery, or long-term historical metrics materialization.
No provider calls, raw selectors, instance labels or Secret details.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance

_MAX_VAULT_SOURCES = 25
_MAX_BINDINGS = 100
_FRESHNESS = timedelta(hours=24)
_FAMILIES = {
    'metrics_source': ('vault-telemetry-v1', 'Metrics'),
    'alert_source': ('vault-alerts-v1', 'Alert'),
}


def _utc(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _family(status: str, name: str, *, sources: int | None = None,
            configured: int | None = None, qualified: int | None = None) -> dict[str, Any]:
    label = {
        'qualified': f'{name} Binding Qualified',
        'partial': f'{name} Binding Partial',
        'not_bound': f'{name} Not Bound',
        'needs_validation': f'{name} Validation Required',
        'not_configured': 'Vault Provider Not Configured',
        'blocked': f'{name} Binding Coverage Blocked',
        'unavailable': f'{name} Binding Evidence Unavailable',
    }[status]
    return {
        'status': status,
        'label': label,
        'eligible_vault_sources': sources,
        'configured_vault_sources': configured,
        'qualified_vault_sources': qualified,
        'coverage': (
            f'{qualified} / {sources}' if status in {'qualified', 'partial'}
            and qualified is not None and sources is not None else 'Not Qualified'
        ),
        'evidence_basis': 'Committed IntegrationBinding validation; not live telemetry',
    }


def _result(status: str) -> dict[str, Any]:
    return {
        'metrics': _family(status, 'Metrics'),
        'alerts': _family(status, 'Alert'),
        'basis': 'Bounded current Vault source and committed integration binding status',
    }


def build_vault_binding_coverage(*, now: datetime | None = None) -> dict[str, Any]:
    """Project only canonical Vault IDs and profile-qualified validation metadata."""
    instant = _utc(now or datetime.now(UTC))
    if instant is None:
        return _result('unavailable')
    try:
        tables = set(inspect(db.engine).get_table_names())
        if not {'integration_instances', 'integration_bindings'}.issubset(tables):
            return _result('unavailable')
        vault_ids = db.session.execute(
            select(IntegrationInstance.id)
            .where(
                IntegrationInstance.integration_type == 'secrets_pki',
                IntegrationInstance.provider_key == 'vault',
                IntegrationInstance.enabled.is_(True),
                IntegrationInstance.lifecycle_status == 'active',
            )
            .order_by(IntegrationInstance.id)
            .limit(_MAX_VAULT_SOURCES + 1)
        ).scalars().all()
        if len(vault_ids) > _MAX_VAULT_SOURCES:
            return _result('blocked')
        if not vault_ids:
            return _result('not_configured')

        rows = db.session.execute(
            select(
                IntegrationBinding.asset_key,
                IntegrationBinding.validation_profile,
                IntegrationBinding.validation_status,
                IntegrationBinding.last_validated_at,
                IntegrationInstance.integration_type,
            )
            .join(IntegrationInstance,
                  IntegrationInstance.id == IntegrationBinding.integration_instance_id)
            .where(
                IntegrationBinding.asset_type == 'vault_instance',
                IntegrationBinding.asset_key.in_([str(source_id) for source_id in vault_ids]),
                IntegrationBinding.enabled.is_(True),
                IntegrationInstance.integration_type.in_(tuple(_FAMILIES)),
                IntegrationInstance.enabled.is_(True),
                IntegrationInstance.lifecycle_status == 'active',
            )
            .limit(_MAX_BINDINGS + 1)
        ).all()
        if len(rows) > _MAX_BINDINGS:
            return _result('blocked')
        groups: dict[str, dict[str, list[tuple[str, datetime | None]]]] = {
            family: defaultdict(list) for family in _FAMILIES
        }
        for asset_key, profile, status, observed_at, family in rows:
            if family not in _FAMILIES:
                continue
            # Exact stored asset identity; never accept labels or leading-zero alias.
            groups[family][asset_key].append(
                (str(status or ''), _utc(observed_at)
                 if profile == _FAMILIES[family][0] else None)
            )

        posture: dict[str, Any] = {
            'basis': 'Committed binding validation is independent of Vault API, history and AlertCases',
        }
        for family, (_profile, name) in _FAMILIES.items():
            bound = groups[family]
            qualified = set()
            for identity, assessments in bound.items():
                # Multiple independently ready sources require explicit precedence
                # and cannot silently be portrayed as single-source qualification.
                matching = [
                    1 for status, checked_at in assessments
                    if status == 'ready' and checked_at is not None
                    and timedelta(0) <= instant - checked_at <= _FRESHNESS
                ]
                if len(matching) == 1:
                    qualified.add(identity)
            configured_count = len(bound)
            qualified_count = len(qualified)
            if not configured_count:
                status = 'not_bound'
            elif qualified_count == len(vault_ids) and configured_count == len(vault_ids):
                status = 'qualified'
            elif qualified_count:
                status = 'partial'
            else:
                status = 'needs_validation'
            posture['metrics' if family == 'metrics_source' else 'alerts'] = _family(
                status, name,
                sources=len(vault_ids), configured=configured_count,
                qualified=qualified_count,
            )
        return posture
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return _result('unavailable')
