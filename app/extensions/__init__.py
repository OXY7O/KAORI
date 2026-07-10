from app.extensions.db import db
from app.extensions.limiter import limiter, register_rate_limit_handlers
from app.extensions.login import login_manager
from app.extensions.migrate import migrate

__all__ = ['db', 'limiter', 'login_manager', 'migrate', 'register_rate_limit_handlers']
