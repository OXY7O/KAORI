import os
from datetime import datetime

from flask import Flask, render_template, request
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix

from app.alertmanager.routes import alertmanager_bp
from app.analytics.routes import analytics_bp
from app.automation_control.routes import automation_control_bp
from app.auth.routes import auth_bp
from app.cluster.constants import get_environment_label
from app.cluster.onboarding import build_cluster_onboarding_context
from app.cluster.routes import cluster_bp
from app.commands import register_commands
from app.common.navigation import build_navigation_breadcrumb
from app.common.timezone import (
    format_user_date,
    format_user_datetime,
    format_user_time,
    normalize_date_format,
    normalize_locale,
    normalize_time_format,
    normalize_timezone_mode,
    normalize_timezone_name,
)
from app.config import CONFIG_MAP
from app.dashboards.kubernetes.routes import kubernetes_dashboard_bp
from app.extensions import db, init_celery, limiter, login_manager, migrate, register_rate_limit_handlers
from app.governance.routes import governance_bp
from app.health import health_bp
from app.integrations.routes import integrations_bp
from app.intelligence.routes import intelligence_bp
from app.inventory.routes import inventory_bp
from app.kubernetes_operations.routes import kubernetes_operations_bp
from app.notifications.routes import notifications_bp
from app.notifications.service import (
    get_navigation_notification_context,
    pop_quick_action_feedback,
)
from app.prometheus.routes import prometheus_bp
from app.reports.routes import reports_bp
from app.integrations.resolver_bootstrap import init_resolver_registry
from app.settings import bp as settings_bp
from app.users.routes import bp as users_bp
from app.welcome.routes import welcome_bp


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
                    'total_count': 0,
                    'display_limit': 8,
                }

            return get_navigation_notification_context(
                user_id=current_user.id,
            )

        def load_quick_action_feedback():
            if not current_user.is_authenticated:
                return None

            return pop_quick_action_feedback()

        current_timezone = (
            normalize_timezone_name(getattr(current_user, 'timezone', 'UTC'))
            if current_user.is_authenticated
            else 'UTC'
        )
        current_timezone_mode = (
            normalize_timezone_mode(getattr(current_user, 'timezone_mode', 'manual'))
            if current_user.is_authenticated
            else 'manual'
        )
        current_locale = (
            normalize_locale(getattr(current_user, 'locale', 'en-US')) if current_user.is_authenticated else 'en-US'
        )
        current_date_format = (
            normalize_date_format(getattr(current_user, 'date_format', 'day_month_year'))
            if current_user.is_authenticated
            else 'day_month_year'
        )
        current_time_format = (
            normalize_time_format(getattr(current_user, 'time_format', '24h'))
            if current_user.is_authenticated
            else '24h'
        )

        return {
            'app_version': app.config['APP_VERSION'],
            'current_year': datetime.now().year,
            'current_timezone': current_timezone,
            'current_timezone_mode': current_timezone_mode,
            'current_locale': current_locale,
            'current_date_format': current_date_format,
            'current_time_format': current_time_format,
            'csrf_token': generate_csrf,
            'load_navigation_notification_context': load_navigation_notification_context,
            'load_quick_action_feedback': load_quick_action_feedback,
            'cluster_onboarding': build_cluster_onboarding_context(),
            'navigation_breadcrumb': build_navigation_breadcrumb(
                request.endpoint,
                request.path,
            ),
        }

    def _user_time_preferences():
        if not current_user.is_authenticated:
            return {
                'timezone_name': 'UTC',
                'locale': 'en-US',
                'date_format': 'day_month_year',
                'time_format': '24h',
            }

        return {
            'timezone_name': normalize_timezone_name(getattr(current_user, 'timezone', 'UTC')),
            'locale': normalize_locale(getattr(current_user, 'locale', 'en-US')),
            'date_format': normalize_date_format(getattr(current_user, 'date_format', 'day_month_year')),
            'time_format': normalize_time_format(getattr(current_user, 'time_format', '24h')),
        }

    @app.template_filter('environment_name')
    def environment_name_filter(value, empty='Not specified'):
        return get_environment_label(value, empty=empty)

    @app.template_filter('user_datetime')
    def user_datetime_filter(value, empty='-', include_seconds=False, include_timezone=True):
        preferences = _user_time_preferences()
        return format_user_datetime(
            value,
            preferences['timezone_name'],
            date_format=preferences['date_format'],
            time_format=preferences['time_format'],
            locale=preferences['locale'],
            include_seconds=include_seconds,
            include_timezone=include_timezone,
            empty=empty,
        )

    @app.template_filter('user_date')
    def user_date_filter(value, empty='-'):
        preferences = _user_time_preferences()
        return format_user_date(
            value,
            preferences['timezone_name'],
            date_format=preferences['date_format'],
            locale=preferences['locale'],
            empty=empty,
        )

    @app.template_filter('user_time')
    def user_time_filter(value, empty='-', include_seconds=False, include_timezone=True):
        preferences = _user_time_preferences()
        return format_user_time(
            value,
            preferences['timezone_name'],
            time_format=preferences['time_format'],
            include_seconds=include_seconds,
            include_timezone=include_timezone,
            empty=empty,
        )

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

    # Build the resolver registry before Celery so web and worker runtimes use the same fail-closed configuration.
    init_resolver_registry(app)

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
    app.register_blueprint(welcome_bp)
    app.register_blueprint(kubernetes_dashboard_bp)
    app.register_blueprint(cluster_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(governance_bp)
    app.register_blueprint(kubernetes_operations_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(intelligence_bp)
    app.register_blueprint(automation_control_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(prometheus_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(alertmanager_bp)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template('errors/403.html'), 403

    register_commands(app)

    return app
