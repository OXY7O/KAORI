from .routes import bp
from .secret_reveal import bp as secret_reveal_bp
from .data_lifecycle import bp as data_lifecycle_bp

bp.register_blueprint(secret_reveal_bp, url_prefix='/secret-reveal')
bp.register_blueprint(data_lifecycle_bp, url_prefix='/data-lifecycle')

__all__ = ['bp']
