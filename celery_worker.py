from app import create_app

flask_app = create_app()
celery_app = flask_app.extensions['celery']
# Import configured task modules before the worker starts consuming queues so a
# restarted worker cannot accept messages with a stale/partial task registry.
celery_app.loader.import_default_modules()

__all__ = ['celery_app', 'flask_app']
