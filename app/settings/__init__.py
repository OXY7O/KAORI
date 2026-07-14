from .routes import bp
from .secret_reveal import bp as secret_reveal_bp

bp.register_blueprint(secret_reveal_bp, url_prefix='/secret-reveal')

__all__ = ['bp']
