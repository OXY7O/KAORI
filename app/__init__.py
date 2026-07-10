import os
from datetime import datetime

from flask import Flask, render_template
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.alertmanager.routes import alertmanager_bp
from app.analytics.routes import analytics_bp
from app.auth.routes import auth_bp
from app.cluster.onboarding import build_cluster_onboarding_context
from app.cluster.routes import cluster_bp
from app.commands import register_commands
from app.config import CONFIG_MAP
from app.dashboard.routes import dashboard_bp
from app.extensions import db, init_celery, limiter, login_manager, migrate, register_rate_limit_handlers
from app.governance.routes import governance_bp
from app.health import health_bp
from app.intelligence.routes import intelligence_bp
from app.inventory.routes import inventory_bp
from app.notifications.routes import notifications_bp
from app.notifications.service import get_navigation_notification_context
from app.prometheus.routes import prometheus_bp
from app.reports.routes import reports_bp
from app.settings import bp as settings_bp


def create_app(config_name: str | None = None):
    # Create Flask application instance
    app = Flask(__name__)

    # Context processor to inject global variables into templates
    @app.context_processor
    def inject_globals():
        def load_navigation_notification_context():
            if not current_user.is_authenticated:
                return {
                    'items': [],
                    'unread_count': 0,
                }

            return get_navigation_notification_context(
                user_id=current_user.id,
            )

        return {
            'app_version': app.config['APP_VERSION'],
            'current_year': datetime.now().year,
            'load_navigation_notification_context': load_navigation_notification_context,
            'cluster_onboarding': build_cluster_onboarding_context(),
        }

    # Load configuration based on APP_ENV environment variable
    env = config_name or os.getenv('APP_ENV', 'development')

    if env not in CONFIG_MAP:
        raise ValueError(f'Invalid APP_ENV: {env}. Must be one of: {", ".join(CONFIG_MAP.keys())}')

    app.config.from_object(CONFIG_MAP[env])

    if app.config.get('PROXY_FIX_ENABLED'):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config.get('PROXY_FIX_X_FOR', 1),
            x_proto=app.config.get('PROXY_FIX_X_PROTO', 1),
            x_host=app.config.get('PROXY_FIX_X_HOST', 1),
            x_port=app.config.get('PROXY_FIX_X_PORT', 1),
            x_prefix=app.config.get('PROXY_FIX_X_PREFIX', 0),
        )

    # Initialize Celery before request handlers enqueue background tasks.
    init_celery(app)

    # Initialize database
    db.init_app(app)

    # Initialize login manager
    login_manager.init_app(app)

    # Initialize migration
    migrate.init_app(app, db)

    # Initialize rate limiter
    limiter.init_app(app)
    register_rate_limit_handlers(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(cluster_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(governance_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(intelligence_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(prometheus_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(alertmanager_bp)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template('errors/403.html'), 403

    register_commands(app)

    return app
