from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.extensions.db import db
from app.models.report import ReportSchedule
from app.reports.schedules.presentation import serialize_schedule
from app.reports.schedules.support import get_cluster_map, get_delivery_channel_options, parse_optional_int
from app.reports.scope import KUBERNETES_CLUSTER_ASSET_TYPE

def _get_schedule_counts() -> tuple[int, int]:
    total, active = db.session.execute(
        select(
            func.count(ReportSchedule.id),
            func.count(ReportSchedule.id).filter(ReportSchedule.is_enabled.is_(True)),
        )
    ).one()
    return int(total or 0), int(active or 0)


def _get_schedule_filter_context() -> list[dict[str, Any]]:
    # Only distinct asset references are needed for historical/deleted filters.
    keys = db.session.execute(
        select(
            ReportSchedule.scope_asset_type,
            ReportSchedule.scope_asset_id,
            ReportSchedule.cluster_id,
            ReportSchedule.scope_asset_label_snapshot,
        ).distinct()
    ).all()
    result: list[dict[str, Any]] = []
    for asset_type, asset_id, cluster_id, label in keys:
        selected_type = str(asset_type or KUBERNETES_CLUSTER_ASSET_TYPE)
        selected_id = str(asset_id or cluster_id or '')
        if selected_id:
            result.append({
                'scope_asset_filter_key': f'{selected_type}:{selected_id}',
                'scope_label': selected_type.replace('_', ' ').title(),
                'scope': str(label or selected_id),
            })
    return result


def _get_run_schedule_options(selected_id: str) -> list[dict[str, Any]]:
    rows = db.session.execute(
        select(ReportSchedule.id, ReportSchedule.name)
        .order_by(ReportSchedule.created_at.desc(), ReportSchedule.id.desc())
        .limit(200)
    ).all()
    options = [{'id': item_id, 'name': name} for item_id, name in rows]
    selected = parse_optional_int(selected_id)
    if selected is not None and all(item['id'] != selected for item in options):
        row = db.session.get(ReportSchedule, selected)
        if row is not None:
            options.append({'id': row.id, 'name': row.name})
    return options


def _serialize_schedule_rows(schedules: list[ReportSchedule]) -> list[dict[str, Any]]:
    cluster_map = get_cluster_map([item.cluster_id for item in schedules if item.cluster_id])
    delivery_label_map = {
        int(item['channel_id']): f'{item["label"]} · {item["provider"]}' for item in get_delivery_channel_options()
    }
    return [serialize_schedule(item, cluster_map, delivery_label_map) for item in schedules]


