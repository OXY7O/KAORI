from app.platform_operations.kubernetes.routes import bp
from app.platform_operations.kubernetes.secret_reveal.routes import bp as secret_reveal_bp

bp.register_blueprint(secret_reveal_bp, url_prefix='/secret-reveal')

__all__ = ['bp']
