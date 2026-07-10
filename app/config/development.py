import os

from app.config.default import Config


class DevelopmentConfig(Config):
    DEBUG = True

    REPORT_STORAGE_BACKEND = (
        os.getenv(
            'DEV_REPORT_STORAGE_BACKEND',
            Config.REPORT_STORAGE_BACKEND,
        )
        .strip()
        .lower()
    )

    REPORT_LOCAL_STORAGE_DIR = os.getenv(
        'DEV_REPORT_LOCAL_STORAGE_DIR',
        Config.REPORT_LOCAL_STORAGE_DIR,
    )
