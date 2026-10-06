from __future__ import annotations

from flask import Blueprint

from app.access.activity_audit import bp as activity_audit_bp
from app.access.overview import bp as overview_bp
from app.access.permissions import bp as permissions_bp
from app.access.roles import bp as roles_bp

bp = Blueprint('access', __name__, url_prefix='/access')

bp.register_blueprint(overview_bp)
bp.register_blueprint(activity_audit_bp, url_prefix='/activity-audit')
bp.register_blueprint(roles_bp, url_prefix='/roles')
bp.register_blueprint(permissions_bp, url_prefix='/permissions')

__all__ = ['bp']
