from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = ROOT / 'deploy' / 'server'
EDGE_ROOT = ROOT / 'example' / 'shared-edge'
SERVER_COMPOSE = SERVER_ROOT / 'compose.server.yml'
SERVER_DEPLOY = SERVER_ROOT / 'deploy.sh'
SERVER_VERIFY = SERVER_ROOT / 'verify.sh'
UAT_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
EDGE_COMPOSE = EDGE_ROOT / 'compose.yml'
EDGE_PREPARE = EDGE_ROOT / 'prepare.sh'
EDGE_PUBLISH = EDGE_ROOT / 'publish-container.sh'
EDGE_APPLY = EDGE_ROOT / 'apply.sh'
EDGE_VERIFY = EDGE_ROOT / 'verify.sh'
EDGE_KAORI_CUTOVER = EDGE_ROOT / 'kaori-cutover-example.sh'
EDGE_NGINX_ENTRYPOINT = EDGE_ROOT / 'nginx-entrypoint.sh'
EDGE_CERTBOT_ENTRYPOINT = EDGE_ROOT / 'certbot-entrypoint.sh'
EDGE_README = EDGE_ROOT / 'README.md'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _service_block(source: str, service: str, next_service: str | None = None) -> str:
    start = source.index(f'  {service}:')
    if next_service is None:
        return source[start:]
    return source[start : source.index(f'  {next_service}:', start)]


def test_standalone_edge_is_an_example_not_a_kaori_deployment_component() -> None:
    required = (
        EDGE_COMPOSE,
        EDGE_PREPARE,
        EDGE_PUBLISH,
        EDGE_APPLY,
        EDGE_VERIFY,
        EDGE_KAORI_CUTOVER,
        EDGE_NGINX_ENTRYPOINT,
        EDGE_CERTBOT_ENTRYPOINT,
        EDGE_README,
        EDGE_ROOT / 'edge.env.example',
        EDGE_ROOT / 'sites' / 'kaori.env.example',
        EDGE_ROOT / 'sites' / 'n8n.env.example',
    )
    for path in required:
        assert path.is_file(), f'missing standalone edge example: {path.relative_to(ROOT)}'

    assert not (ROOT / 'deploy' / 'edge').exists()
    assert not (ROOT / '.github' / 'workflows' / 'deploy-shared-edge.yml').exists()


def test_kaori_server_compose_has_no_public_edge_dependency() -> None:
    source = _read(SERVER_COMPOSE)
    web = _service_block(source, 'web', 'worker')

    assert '  nginx:' not in source
    assert '  certbot:' not in source
    assert 'edge-public' not in source
    assert 'edge_public' not in source
    assert '"80:8080"' not in source
    assert '"443:8443"' not in source
    assert 'kaori_vps_letsencrypt' not in source
    assert 'kaori_vps_acme_webroot' not in source

    assert 'ports: !reset []' in web
    assert 'expose:' in web
    assert '- "5000"' in web
    assert 'kaori_production' not in web


def test_kaori_deploy_stops_at_application_runtime_health() -> None:
    deploy = _read(SERVER_DEPLOY)
    workflow = _read(UAT_WORKFLOW)

    for forbidden in (
        'Nginx',
        'Certbot',
        'KAORI_PUBLIC_DOMAIN',
        'KAORI_PUBLIC_IP',
        'KAORI_LETSENCRYPT_EMAIL',
        'KAORI_NGINX_IMAGE',
        'KAORI_CERTBOT_IMAGE',
        'edge-public',
        'deploy/nginx',
        'deploy/edge',
        'public HTTPS readiness',
        'renewal-dry-run',
    ):
        assert forbidden not in deploy

    assert 'Internal runtime PASS' in deploy
    assert 'KAORI application runtime healthy' in deploy
    assert '--remove-orphans' not in deploy

    assert 'KAORI_LETSENCRYPT_EMAIL' not in workflow
    assert 'deploy/nginx' not in workflow
    assert 'deploy/edge' not in workflow
    assert 'example/shared-edge' not in workflow


def test_standalone_edge_is_digest_pinned_socketless_and_owns_public_ports() -> None:
    source = _read(EDGE_COMPOSE)
    nginx = _service_block(source, 'nginx', 'certbot')
    certbot = _service_block(source, 'certbot')

    assert '${EDGE_NGINX_IMAGE:?' in nginx
    assert '${EDGE_CERTBOT_IMAGE:?' in certbot
    assert '"80:8080"' in nginx
    assert '"443:8443"' in nginx
    assert '/var/run/docker.sock' not in source
    assert '${EDGE_CERTIFICATE_DIR:-/opt/shared-edge/state/letsencrypt}' in source
    assert '${EDGE_ACME_WEBROOT_DIR:-/opt/shared-edge/state/acme-webroot}' in source
    assert '${EDGE_SITES_DIR:-/opt/shared-edge/config/sites}' in source
    assert 'name: edge-public' in source
    assert 'external: true' in source
    assert 'read_only: true' in nginx
    assert 'no-new-privileges:true' in source


def test_generic_edge_prepare_and_publish_have_no_kaori_knowledge() -> None:
    prepare = _read(EDGE_PREPARE)
    publish = _read(EDGE_PUBLISH)

    for source in (prepare, publish):
        assert '/etc/kaori' not in source
        assert 'kaori-production' not in source
        assert 'kaori-vps-letsencrypt' not in source
        assert 'KAORI_' not in source

    assert 'docker network create edge-public' in prepare
    assert 'compose.yml' in prepare
    assert 'docker network connect --alias' in publish
    assert '--container' in publish
    assert '--domain' in publish
    assert '--port' in publish
    assert 'EDGE_UPSTREAM=' in publish


def test_kaori_specific_legacy_migration_is_explicitly_an_example() -> None:
    source = _read(EDGE_KAORI_CUTOVER)

    assert 'kaori-production' in source
    assert 'kaori-vps-letsencrypt' in source
    assert 'kaori.cloud' in source
    assert '--alias kaori-web' in source
    assert '--port 5000' in source
    assert '--health-path /health/ready' in source
    assert 'com.docker.compose.service=nginx' in source
    assert 'com.docker.compose.service=certbot' in source
    assert 'rollback' in source.lower()
    assert 'docker start' in source
    assert 'docker stop' in source


def test_n8n_is_documentation_only_and_not_a_kaori_runtime_dependency() -> None:
    readme = _read(EDGE_README)
    n8n = _read(EDGE_ROOT / 'sites' / 'n8n.env.example')
    kaori_runtime = '\n'.join((_read(SERVER_COMPOSE), _read(SERVER_DEPLOY), _read(SERVER_VERIFY), _read(UAT_WORKFLOW)))

    assert 'auto.kaori.cloud' in readme
    assert 'n8n is **not part of KAORI**' in readme
    assert 'EDGE_DOMAIN=auto.kaori.cloud' in n8n
    assert 'EDGE_UPSTREAM=n8n' in n8n
    assert 'EDGE_UPSTREAM_PORT=5678' in n8n
    assert 'N8N_WEBHOOK_URL=https://auto.kaori.cloud/' in readme
    assert 'n8n' not in kaori_runtime.lower()
    assert 'auto.kaori.cloud' not in kaori_runtime


def test_standalone_edge_verifier_preserves_public_security_checks() -> None:
    verify = _read(EDGE_VERIFY)

    for marker in (
        'for site_file in "$EDGE_SITES_DIR"/*.env',
        'getent ahostsv4',
        'HTTP redirect PASS',
        'TLS PASS',
        'HTTPS readiness PASS',
        'Unknown Host/SNI rejection PASS',
        'certbot renew --dry-run',
    ):
        assert marker in verify


def test_certbot_rescans_new_tls_registrations_without_waiting_for_renewal_window() -> None:
    certbot = _read(EDGE_CERTBOT_ENTRYPOINT)

    assert 'next_renewal_epoch=0' in certbot
    assert 'now_epoch="$(date +%s)"' in certbot
    assert 'if [ "$now_epoch" -ge "$next_renewal_epoch" ]; then' in certbot
    assert 'next_renewal_epoch=$((now_epoch + renew_interval))' in certbot
    assert 'sleep "$renew_interval"' not in certbot
    assert 'sleep "$issue_retry_interval"' in certbot


def test_standalone_edge_runtime_reconciles_sites_without_docker_socket() -> None:
    nginx = _read(EDGE_NGINX_ENTRYPOINT)
    certbot = _read(EDGE_CERTBOT_ENTRYPOINT)

    assert 'EDGE_SITES_DIR' in nginx
    assert 'nginx -t' in nginx
    assert 'nginx -s reload' in nginx
    assert 'EDGE_WEBSOCKET' in nginx
    assert '/var/run/docker.sock' not in nginx

    assert 'EDGE_SITES_DIR' in certbot
    assert 'certbot certonly' in certbot
    assert 'certbot renew' in certbot
    assert '/var/run/docker.sock' not in certbot
