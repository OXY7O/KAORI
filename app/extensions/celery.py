from __future__ import annotations

from typing import Any

from celery import Celery, Task
from flask import Flask


class FlaskContextTask(Task):
    """Run every Celery task inside the KAORI Flask application context."""

    abstract = True
    flask_app: Flask

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        with self.flask_app.app_context():
            return self.run(*args, **kwargs)


def init_celery(app: Flask) -> Celery:
    task_class = type(
        'KAORIFlaskTask',
        (FlaskContextTask,),
        {
            'flask_app': app,
            '__module__': __name__,
        },
    )

    celery_app = Celery(
        app.import_name,
        task_cls=task_class,
    )
    celery_app.config_from_object(
        app.config['CELERY'],
    )
    celery_app.set_default()

    app.extensions['celery'] = celery_app

    return celery_app
