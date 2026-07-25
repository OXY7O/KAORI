from app.platform_operations.kubernetes import bp as kubernetes_bp
from app.platform_operations.routes import bp

bp.register_blueprint(kubernetes_bp, url_prefix='/kubernetes')

__all__ = ['bp']
