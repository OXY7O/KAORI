from flask import Flask
from app.reports.storage.service import _get_process_storage_status_cache_key


def test_s3_process_cache_identity_follows_shared_fingerprint():
    app = Flask(__name__)
    with app.app_context():
        app.config.update(REPORT_S3_BUCKET='bucket', REPORT_S3_ACCESS_KEY_ID='one', REPORT_S3_SECRET_ACCESS_KEY='first', REPORT_S3_FORCE_PATH_STYLE=False)
        first = _get_process_storage_status_cache_key('s3')
        app.config['REPORT_S3_SECRET_ACCESS_KEY'] = 'second'
        assert _get_process_storage_status_cache_key('s3') != first
        app.config['REPORT_S3_SECRET_ACCESS_KEY'] = 'first'
        app.config['REPORT_S3_FORCE_PATH_STYLE'] = True
        assert _get_process_storage_status_cache_key('s3') != first
        assert 'first' not in str(first)
