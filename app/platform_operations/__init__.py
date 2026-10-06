from app.platform_operations.data_lifecycle import bp as data_lifecycle_bp
from app.platform_operations.global_search.routes import bp as global_search_bp
from app.platform_operations.kubernetes import bp as kubernetes_bp
from app.platform_operations.overview import bp as overview_bp
from app.platform_operations.routes import bp

bp.register_blueprint(overview_bp)
bp.register_blueprint(data_lifecycle_bp, url_prefix='/data-lifecycle')
bp.register_blueprint(global_search_bp)
bp.register_blueprint(kubernetes_bp, url_prefix='/kubernetes')

__all__ = ['bp']
