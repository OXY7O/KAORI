from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VPS_COMPOSE = ROOT / 'deploy' / 'vps' / 'compose.vps.yml'
PRODUCTION_COMPOSE = ROOT / 'compose.production.yml'
GUNICORN_CONFIG = ROOT / 'gunicorn.conf.py'


def _read(path: Path) -> str:
    assert path.is_file(), f'missing required runtime surface: {path.relative_to(ROOT)}'
    return path.read_text(encoding='utf-8')


def _service_block(text: str, service: str, next_service: str | None = None) -> str:
    start = text.index(f'  {service}:')
    if next_service is None:
        return text[start:]
    end = text.index(f'  {next_service}:', start)
    return text[start:end]


def test_nginx_edge_uses_only_minimum_runtime_capabilities() -> None:
    nginx = _service_block(_read(VPS_COMPOSE), 'nginx', 'certbot')

    assert 'read_only: true' in nginx
    assert 'no-new-privileges:true' in nginx
    assert 'cap_drop:' in nginx
    assert '- ALL' in nginx
    assert 'cap_add:' in nginx
    for capability in ('CHOWN', 'SETGID', 'SETUID'):
        assert f'- {capability}' in nginx
    for forbidden in ('NET_ADMIN', 'NET_BIND_SERVICE', 'SYS_ADMIN'):
        assert forbidden not in nginx
    assert '"80:8080"' in nginx
    assert '"443:8443"' in nginx


def test_production_gunicorn_disables_unused_control_socket() -> None:
    gunicorn = _read(GUNICORN_CONFIG)

    assert 'control_socket_disable = True' in gunicorn


def test_read_only_runtime_uses_tmpfs_backed_xdg_cache() -> None:
    compose = _read(PRODUCTION_COMPOSE)
    web = _service_block(compose, 'web', 'worker')

    assert 'XDG_CACHE_HOME: /tmp/.cache' in compose
    assert 'read_only: true' in web
    assert '/tmp:rw,noexec,nosuid,size=128m' in web
