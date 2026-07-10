import os

from app.config.default import Config


class ProductionConfig(Config):
    DEBUG = False

    REPORT_STORAGE_BACKEND = (
        os.getenv(
            'PROD_REPORT_STORAGE_BACKEND',
            Config.REPORT_STORAGE_BACKEND,
        )
        .strip()
        .lower()
    )

    REPORT_LOCAL_STORAGE_DIR = os.getenv(
        'PROD_REPORT_LOCAL_STORAGE_DIR',
        Config.REPORT_LOCAL_STORAGE_DIR,
    )

    REPORT_S3_BUCKET = os.getenv(
        'PROD_REPORT_S3_BUCKET',
        Config.REPORT_S3_BUCKET,
    )

    REPORT_S3_REGION = os.getenv(
        'PROD_REPORT_S3_REGION',
        Config.REPORT_S3_REGION,
    )

    REPORT_S3_ACCESS_KEY_ID = (
        os.getenv(
            'PROD_REPORT_S3_ACCESS_KEY_ID',
            Config.REPORT_S3_ACCESS_KEY_ID or '',
        )
        or None
    )

    REPORT_S3_SECRET_ACCESS_KEY = (
        os.getenv(
            'PROD_REPORT_S3_SECRET_ACCESS_KEY',
            Config.REPORT_S3_SECRET_ACCESS_KEY or '',
        )
        or None
    )

    REPORT_S3_ENDPOINT_URL = (
        os.getenv(
            'PROD_REPORT_S3_ENDPOINT_URL',
            Config.REPORT_S3_ENDPOINT_URL or '',
        )
        or None
    )

    REPORT_S3_PREFIX = (
        os.getenv(
            'PROD_REPORT_S3_PREFIX',
            Config.REPORT_S3_PREFIX,
        )
        .strip()
        .strip('/')
    )
