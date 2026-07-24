from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_application_factory_initializes_extensions_before_web_domains() -> None:
    source = (ROOT / 'app/__init__.py').read_text(encoding='utf-8')
    assert 'from app.analytics.routes import' not in source
    assert 'from app.bootstrap.presentation import register_presentation' in source
    assert source.index('_initialize_extensions(app)') < source.index(
        'from app.bootstrap.presentation import register_presentation'
    )
    assert source.index('_initialize_extensions(app)') < source.index('register_blueprints(app)')
    assert source.index('init_resolver_registry(app)') < source.index('init_celery(app)')


def test_blueprint_imports_have_one_explicit_bootstrap_owner() -> None:
    source = (ROOT / 'app/bootstrap/blueprints.py').read_text(encoding='utf-8')
    assert 'def register_blueprints(app: Flask)' in source
    assert 'from app.inventory.routes import inventory_bp' in source
    assert 'from app.analytics.routes import analytics_bp' in source
    assert 'app.register_blueprint' in source


def test_global_template_presentation_is_outside_factory() -> None:
    factory = (ROOT / 'app/__init__.py').read_text(encoding='utf-8')
    presentation = (ROOT / 'app/bootstrap/presentation.py').read_text(encoding='utf-8')
    assert '@app.context_processor' not in factory
    assert 'def register_presentation(app: Flask)' in presentation
    assert '@app.context_processor' in presentation
