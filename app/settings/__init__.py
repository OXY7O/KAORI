from app.settings.data_lifecycle.routes import bp as data_lifecycle_bp

from .routes import bp

bp.register_blueprint(data_lifecycle_bp, url_prefix='/data-lifecycle')

__all__ = ['bp']
