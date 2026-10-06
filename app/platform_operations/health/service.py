from __future__ import annotations

from typing import Any

from flask import current_app
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db


def check_database() -> tuple[bool, str]:
    try:
        db.session.execute(text('SELECT 1'))
        return True, 'ok'
    except SQLAlchemyError:
        db.session.rollback()
        return False, 'unavailable'


def check_redis() -> tuple[bool, str]:
    redis_url = (current_app.config.get('REDIS_URL') or '').strip()
    if not redis_url:
        return True, 'not_configured'

    try:
        client = Redis.from_url(
            redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return True, 'ok'
    except RedisError:
        return False, 'unavailable'


def build_readiness_status() -> tuple[dict[str, Any], int]:
    database_ready, database_status = check_database()
    redis_ready, redis_status = check_redis()
    ready = database_ready and redis_ready

    payload = {
        'status': 'ready' if ready else 'not_ready',
        'database': database_status,
        'redis': redis_status,
    }

    return payload, 200 if ready else 503
