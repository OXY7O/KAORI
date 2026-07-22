import os

from app.config.default import BASE_DIR, Config


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False

    SQLALCHEMY_DATABASE_URI = os.getenv(
        'TEST_DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/kaori_test',
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.getenv(
        'TEST_SECRET_KEY',
        'test-secret-key',
    )

    REPORT_STORAGE_BACKEND = (
        os.getenv(
            'TEST_REPORT_STORAGE_BACKEND',
            'local',
        )
        .strip()
        .lower()
    )

    REPORT_LOCAL_STORAGE_DIR = os.getenv(
        'TEST_REPORT_LOCAL_STORAGE_DIR',
        str(
            BASE_DIR / 'instance' / 'test-reports',
        ),
    )


    REPORT_RENDER_STAGING_DIR = os.getenv(
        'TEST_REPORT_RENDER_STAGING_DIR',
        str(
            BASE_DIR / 'instance' / 'test-report-render-staging',
        ),
    )

    REPORT_DOWNLOAD_CACHE_DIR = os.getenv(
        'TEST_REPORT_DOWNLOAD_CACHE_DIR',
        str(
            BASE_DIR / 'instance' / 'test-report-download-cache',
        ),
    )

    ARCHIVE_STORAGE_BACKEND = 'local'
    ARCHIVE_LOCAL_STORAGE_DIR = os.getenv(
        'TEST_ARCHIVE_LOCAL_STORAGE_DIR',
        str(BASE_DIR / 'instance' / 'test-archives'),
    )
    ARCHIVE_DOWNLOAD_CACHE_DIR = os.getenv(
        'TEST_ARCHIVE_DOWNLOAD_CACHE_DIR',
        str(BASE_DIR / 'instance' / 'test-archive-download-cache'),
    )
    ARCHIVE_STAGING_DIR = os.getenv(
        'TEST_ARCHIVE_STAGING_DIR',
        str(BASE_DIR / 'instance' / 'test-archive-staging'),
    )
    ACTIVITY_RETENTION_SCHEDULE_ENABLED = False
    CELERY = {**Config.CELERY, 'beat_schedule': {}}
