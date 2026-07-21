from __future__ import annotations

from flask import Blueprint, make_response, redirect, request, url_for

from app.alertmanager.resolver import resolve_alertmanager_sources
from app.prometheus.repository import resolve_instance_for_cluster

legacy_integrations_bp = Blueprint('legacy_integrations', __name__)


def _redirect(location: str):
    response = make_response(redirect(location, code=302))
    response.headers['Deprecation'] = 'true'
    response.headers['Sunset'] = 'Wed, 31 Dec 2026 23:59:59 GMT'
    response.headers['Cache-Control'] = 'no-store'
    return response


def _with_query(location: str) -> str:
    query = request.query_string.decode('utf-8').strip()
    if not query:
        return location
    separator = '&' if '?' in location else '?'
    return f'{location}{separator}{query}'


@legacy_integrations_bp.get('/prometheus')
@legacy_integrations_bp.get('/prometheus/')
@legacy_integrations_bp.get('/prometheus/instances')
def prometheus_landing():
    return _redirect(_with_query(url_for('integrations.prometheus')))


@legacy_integrations_bp.get('/prometheus/instances/<int:instance_id>')
@legacy_integrations_bp.get('/prometheus/instances/<int:instance_id>/edit')
@legacy_integrations_bp.get('/prometheus/instances/<int:instance_id>/<path:_legacy_path>')
def prometheus_instance(instance_id: int, _legacy_path: str | None = None):
    return _redirect(
        _with_query(url_for('prometheus.instance_detail', instance_id=instance_id))
    )


@legacy_integrations_bp.get('/prometheus/cluster/<string:cluster_id>')
@legacy_integrations_bp.get('/prometheus/cluster/<string:cluster_id>/<path:_legacy_path>')
def prometheus_cluster(cluster_id: str, _legacy_path: str | None = None):
    instance = resolve_instance_for_cluster(cluster_id)
    if instance is None:
        location = url_for('integrations.bind_prometheus_source', scope_key=cluster_id)
    else:
        location = url_for('prometheus.instance_detail', instance_id=instance.id)
    return _redirect(_with_query(location))


@legacy_integrations_bp.get('/prometheus/<path:_legacy_path>')
def prometheus_unknown(_legacy_path: str):
    return _redirect(_with_query(url_for('integrations.prometheus')))


@legacy_integrations_bp.get('/alertmanager')
@legacy_integrations_bp.get('/alertmanager/')
@legacy_integrations_bp.get('/alertmanager/instances')
def alertmanager_landing():
    return _redirect(_with_query(url_for('integrations.alertmanager')))


@legacy_integrations_bp.get('/alertmanager/instances/<int:instance_id>')
@legacy_integrations_bp.get('/alertmanager/instances/<int:instance_id>/<path:_legacy_path>')
def alertmanager_instance(instance_id: int, _legacy_path: str | None = None):
    return _redirect(
        _with_query(url_for('alertmanager.instance_detail', instance_id=instance_id))
    )


@legacy_integrations_bp.get('/alertmanager/cluster/<string:cluster_id>')
@legacy_integrations_bp.get('/alertmanager/cluster/<string:cluster_id>/<path:_legacy_path>')
def alertmanager_cluster(cluster_id: str, _legacy_path: str | None = None):
    resolution = resolve_alertmanager_sources(
        scope_type='kubernetes_cluster',
        scope_key=cluster_id,
    )
    selected = resolution.selected or (resolution.candidates[0] if resolution.candidates else None)
    if selected is not None:
        location = url_for('alertmanager.instance_detail', instance_id=selected.instance.id)
    else:
        location = url_for('integrations.bind_alertmanager_source', scope_key=cluster_id)
    return _redirect(_with_query(location))


@legacy_integrations_bp.get('/alertmanager/<path:_legacy_path>')
def alertmanager_unknown(_legacy_path: str):
    return _redirect(_with_query(url_for('integrations.alertmanager')))
