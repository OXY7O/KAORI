from flask import Blueprint

health_bp = Blueprint('health', __name__, url_prefix='/health')

from app.health import routes  # noqa: E402, F401
