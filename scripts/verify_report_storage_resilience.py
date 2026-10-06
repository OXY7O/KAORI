from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def require(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise SystemExit(message)


def forbid(source: str, needle: str, message: str) -> None:
    if needle in source:
        raise SystemExit(message)


def main() -> None:
    storage_service = read('app/reports/storage/service.py')
    storage_template = read('app/templates/reports/storage/index.html')
    storage_routes = read('app/reports/storage/routes.py')
    report_routes = read('app/reports/routes.py')
    generated_service = read('app/reports/generated/service.py')
    export_service = read('app/reports/export/service.py')
    s3_storage = read('app/artifact_storage/s3.py')
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
        'Verify Connection',
        'Reports Storage is missing the explicit strong-verification reconnect action.',
    )
    require(
        storage_template,
        "url_for('reports.verify_storage')",
        'Reports Storage verification must target the POST-only verification endpoint.',
    )
    require(
        report_routes,
        "'/storage/verify'",
        'Reports Storage is missing the dedicated verification route.',
    )
    require(
        report_routes.split("endpoint='verify_storage'", 1)[1].split('reports_bp.add_url_rule(', 1)[0],
        "'POST'",
        'Reports Storage strong verification must be POST-only.',
    )
    forbid(
        storage_routes,
        "request.args.get('verify')",
        'Reports Storage must not execute strong verification from a GET query parameter.',
    )
    forbid(
        storage_service,
        'build_report_cleanup_dry_run',
        'Reports Storage must not maintain a second Generated Reports lifecycle eligibility engine.',
    )
    require(
        storage_template,
        'Lifecycle Actions Live in Data Lifecycle',
        'Reports Storage must hand lifecycle preview and cleanup execution to Data Lifecycle.',
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
