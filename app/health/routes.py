from __future__ import annotations

from flask import jsonify

from app.health import health_bp
from app.health.service import build_readiness_status


@health_bp.get('/live')
def live():
    return jsonify({'status': 'ok'}), 200


@health_bp.get('/ready')
def ready():
    payload, status_code = build_readiness_status()
    return jsonify(payload), status_code
