from pathlib import Path
from flask import Flask
from app.reports.storage.service import get_configured_storage_backend_name, build_report_storage_backend
import pytest


def test_unsupported_backend_never_resolves_to_local():
    app = Flask(__name__)
    with app.app_context():
        app.config['REPORT_STORAGE_BACKEND'] = 'S3-typo'
        assert get_configured_storage_backend_name() == 's3-typo'
        with pytest.raises(RuntimeError, match='Unsupported report storage backend'):
            build_report_storage_backend(get_configured_storage_backend_name())
        app.config['REPORT_STORAGE_BACKEND'] = None
        assert get_configured_storage_backend_name() == 'local'


def test_unknown_backend_does_not_project_local_target():
    template = (Path(__file__).resolve().parents[3] / 'app/templates/reports/storage/index.html').read_text()
    assert "elif payload.active_backend == 'local'" in template
    assert 'Unsupported configured backend. Artifact publication is paused' in template
