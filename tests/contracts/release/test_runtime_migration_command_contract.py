from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_validation_uses_kaori_flask_migrate_context() -> None:
    runtime_validation = read('.github/ci/run-runtime-validation.sh')

    assert 'run --rm runtime flask --app run:app db upgrade' in runtime_validation
    assert 'run --rm runtime alembic upgrade head' not in runtime_validation


def test_migration_environment_requires_flask_application_context() -> None:
    app_factory = read('app/__init__.py')
    migration_environment = read('migrations/env.py')

    assert 'migrate.init_app(app, db)' in app_factory
    assert 'from flask import current_app' in migration_environment
    assert "current_app.extensions['migrate']" in migration_environment
