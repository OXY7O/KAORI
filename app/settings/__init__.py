from app.settings.access_compat import bp as access_compat_bp
from app.settings.data_lifecycle_compat import bp as data_lifecycle_bp

from .routes import bp

bp.register_blueprint(data_lifecycle_bp, url_prefix='/data-lifecycle')
bp.register_blueprint(access_compat_bp)

__all__ = ['bp']
