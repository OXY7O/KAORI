from __future__ import annotations

import os

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import CONFIG_MAP
from app.extensions import db, init_celery, limiter, login_manager, migrate, register_rate_limit_handlers


def _apply_proxy_fix(app: Flask) -> None:
    if not app.config.get('PROXY_FIX_ENABLED'):
        return
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=app.config.get('PROXY_FIX_X_FOR', 1),
        x_proto=app.config.get('PROXY_FIX_X_PROTO', 1),
        x_host=app.config.get('PROXY_FIX_X_HOST', 1),
        x_port=app.config.get('PROXY_FIX_X_PORT', 1),
        x_prefix=app.config.get('PROXY_FIX_X_PREFIX', 0),
    )


def _initialize_extensions(app: Flask) -> None:
    from app.integrations.resolver_bootstrap import init_resolver_registry

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    register_rate_limit_handlers(app)

    # The registry must be identical in web and worker processes before Celery
    # imports task modules or request handlers enqueue resolver work.
    init_resolver_registry(app)
    init_celery(app)


def create_app(config_name: str | None = None) -> Flask:
    """Create one fully initialized KAORI Flask application."""
    app = Flask(__name__)
    environment = config_name or os.getenv('APP_ENV', 'development')
    if environment not in CONFIG_MAP:
        choices = ', '.join(CONFIG_MAP)
        raise ValueError(f'Invalid APP_ENV: {environment}. Must be one of: {choices}')

    app.config.from_object(CONFIG_MAP[environment])
    _apply_proxy_fix(app)
    _initialize_extensions(app)

    from app.bootstrap.blueprints import register_blueprints
    from app.bootstrap.presentation import register_presentation
    from app.commands import register_commands

    register_presentation(app)
    register_blueprints(app)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template('errors/403.html'), 403

    register_commands(app)
    return app
