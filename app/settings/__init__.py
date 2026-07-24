from app.settings.data_lifecycle.routes import bp as data_lifecycle_bp
from app.settings.inventory_sync.routes import bp as inventory_sync_bp
from app.settings.secret_reveal.routes import bp as secret_reveal_bp

from .routes import bp

bp.register_blueprint(secret_reveal_bp, url_prefix='/secret-reveal')
bp.register_blueprint(inventory_sync_bp, url_prefix='/inventory-sync')
bp.register_blueprint(data_lifecycle_bp, url_prefix='/data-lifecycle')

__all__ = ['bp']
