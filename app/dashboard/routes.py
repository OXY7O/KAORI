"""Deprecated compatibility imports.

Canonical route ownership now lives in ``app.welcome`` and
``app.dashboards.kubernetes``. The compatibility blueprint preserves legacy
``dashboard.*`` endpoint names while redirecting to canonical routes.
"""

from app.dashboards.kubernetes.routes import kubernetes_dashboard_bp
from app.dashboards.routes import dashboard_compat_bp as dashboard_bp
from app.welcome.routes import welcome_bp

__all__ = ['dashboard_bp', 'kubernetes_dashboard_bp', 'welcome_bp']
