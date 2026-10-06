from __future__ import annotations

from flask import Blueprint, jsonify

from app.platform_operations.health.service import build_readiness_status

health_bp = Blueprint('health', __name__, url_prefix='/health')


@health_bp.get('/live')
def live():
    return jsonify({'status': 'ok'}), 200


@health_bp.get('/ready')
def ready():
    payload, status_code = build_readiness_status()
    return jsonify(payload), status_code
