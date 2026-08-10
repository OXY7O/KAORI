from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def require(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise SystemExit(message)


def main() -> None:
    storage_service = read('app/reports/storage/service.py')
    storage_template = read('app/templates/reports/storage/index.html')
    generated_service = read('app/reports/generated/service.py')
    export_service = read('app/reports/export/service.py')
    s3_storage = read('app/storage/s3.py')
    config = read('app/config/default.py')

    require(
        storage_service,
        'def get_report_storage_backend_status(',
        'Missing canonical report storage availability resolver.',
    )
    require(
        storage_service,
        'def probe_report_artifact(',
        'Missing failure-tolerant report artifact probe.',
    )
    require(
        storage_service,
        "'status': 'Disconnected'",
        'Disconnected storage state is not represented explicitly.',
    )
    require(
        storage_service,
        'Report pages and database records remain available',
        'Storage disconnect copy must preserve page and registry availability.',
    )
    require(
        storage_service,
        "'error': 'Storage backend was unavailable during this integrity check.'",
        'Integrity checks must not expose raw S3 exceptions.',
    )
    require(
        storage_template,
        'report-storage-connectivity-title',
        'Reports Storage is missing the user-friendly connectivity banner.',
    )
    require(
        storage_template,
        'Retry Connection',
        'Reports Storage is missing the explicit reconnect action.',
    )
    require(
        storage_template,
        "backend_status.backend == 's3' and not backend_status.reachable",
        'Reports Storage connectivity banner must be scoped to an unreachable S3 backend.',
    )
    require(
        storage_template,
        '{{ backend_status.title }}',
        'Reports Storage connectivity banner must use the canonical sanitized storage title.',
    )
    require(
        storage_template,
        '{{ backend_status.description }}',
        'Reports Storage connectivity banner must use the canonical sanitized storage description.',
    )
    require(
        generated_service,
        'backend_status = get_report_storage_backend_status()',
        'Generated Reports does not consume the canonical storage state.',
    )
    require(
        generated_service,
        'return probe_report_artifact(file_path)',
        'Generated report detail does not use the safe artifact probe.',
    )
    require(
        export_service,
        "if not bool(backend_status.get('write_available', False)):",
        'Artifact generation must stop before rendering when storage is unavailable.',
    )
    require(
        s3_storage,
        "'connect_timeout': max(int(connect_timeout_seconds), 1)",
        'S3 connect timeout is not bounded.',
    )
    require(
        s3_storage,
        "'read_timeout': max(int(read_timeout_seconds), 1)",
        'S3 read timeout is not bounded.',
    )
    require(
        s3_storage,
        "'total_max_attempts': max(int(max_attempts), 1)",
        'S3 retry policy does not enforce a bounded total attempt count.',
    )
    for setting in (
        'REPORT_S3_CONNECT_TIMEOUT_SECONDS',
        'REPORT_S3_READ_TIMEOUT_SECONDS',
        'REPORT_S3_MAX_ATTEMPTS',
        'REPORT_STORAGE_STATUS_CACHE_SECONDS',
    ):
        require(config, setting, f'Missing report storage resilience setting: {setting}.')

    print(
        'KAORI report storage resilience audit passed: disconnected S3/MinIO is fail-fast, '
        'report pages remain readable, storage-dependent actions degrade safely, and raw backend '
        'exceptions are not exposed to users.'
    )


if __name__ == '__main__':
    main()
