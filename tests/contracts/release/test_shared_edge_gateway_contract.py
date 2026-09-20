from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = ROOT / 'deploy' / 'server'
EDGE_ROOT = ROOT / 'deploy' / 'edge'
SERVER_COMPOSE = SERVER_ROOT / 'compose.server.yml'
SERVER_DEPLOY = SERVER_ROOT / 'deploy.sh'
SERVER_VERIFY = SERVER_ROOT / 'verify.sh'
EDGE_COMPOSE = EDGE_ROOT / 'compose.edge.yml'
EDGE_PREPARE = EDGE_ROOT / 'prepare.sh'
EDGE_APPLY = EDGE_ROOT / 'apply.sh'
EDGE_VERIFY = EDGE_ROOT / 'verify.sh'
EDGE_NGINX_ENTRYPOINT = EDGE_ROOT / 'nginx-entrypoint.sh'
EDGE_CERTBOT_ENTRYPOINT = EDGE_ROOT / 'certbot-entrypoint.sh'
EDGE_README = EDGE_ROOT / 'README.md'
EDGE_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-shared-edge.yml'
UAT_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _service_block(source: str, service: str, next_service: str | None = None) -> str:
    start = source.index(f'  {service}:')
    if next_service is None:
        return source[start:]
    return source[start : source.index(f'  {next_service}:', start)]


def test_shared_edge_has_an_independent_governed_surface() -> None:
    required = (
        EDGE_COMPOSE,
        EDGE_PREPARE,
        EDGE_APPLY,
        EDGE_VERIFY,
        EDGE_NGINX_ENTRYPOINT,
        EDGE_CERTBOT_ENTRYPOINT,
        EDGE_README,
        EDGE_WORKFLOW,
        EDGE_ROOT / 'sites' / 'kaori.env.example',
        EDGE_ROOT / 'sites' / 'n8n.env.example',
    )
    for path in required:
        assert path.is_file(), f'missing shared-edge surface: {path.relative_to(ROOT)}'


def test_kaori_server_compose_is_only_an_edge_consumer() -> None:
    source = _read(SERVER_COMPOSE)
    web = _service_block(source, 'web', 'worker')

    assert '  nginx:' not in source
    assert '  certbot:' not in source
    assert '"80:8080"' not in source
    assert '"443:8443"' not in source
    assert 'kaori_vps_letsencrypt' not in source
    assert 'kaori_vps_acme_webroot' not in source

    assert 'ports: !reset []' in web
    assert '- kaori_production' in web
    assert '- edge_public' in web
    assert 'aliases:' in web
    assert '- kaori-web' in web

    assert 'edge_public:' in source
    assert 'name: edge-public' in source
    assert 'external: true' in source


def test_kaori_deploy_does_not_manage_the_shared_edge() -> None:
    deploy = _read(SERVER_DEPLOY)
    workflow = _read(UAT_WORKFLOW)

    for forbidden in (
        'Starting Compose-managed Nginx and Certbot edge',
        'pull postgres redis nginx certbot',
        'up -d --pull never nginx certbot',
        'KAORI_NGINX_IMAGE',
        'KAORI_CERTBOT_IMAGE',
        'KAORI_LETSENCRYPT_EMAIL',
        'deploy/nginx',
    ):
        assert forbidden not in deploy

    assert '--remove-orphans' not in deploy
    assert 'public HTTPS readiness' in deploy
    assert 'shared edge' in deploy.lower()

    assert 'KAORI_LETSENCRYPT_EMAIL' not in workflow
    assert 'scp "${scp_opts[@]}" -r deploy/nginx' not in workflow


def test_shared_edge_is_digest_pinned_socketless_and_owns_public_ports() -> None:
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

    assert 'edge_public:' in source
    assert 'name: edge-public' in source
    assert 'external: true' in source
    assert 'read_only: true' in nginx
    assert 'no-new-privileges:true' in source


def test_site_registry_is_explicit_and_supports_kaori_and_n8n() -> None:
    kaori = _read(EDGE_ROOT / 'sites' / 'kaori.env.example')
    n8n = _read(EDGE_ROOT / 'sites' / 'n8n.env.example')

    required_keys = (
        'EDGE_DOMAIN=',
        'EDGE_UPSTREAM=',
        'EDGE_UPSTREAM_PORT=',
        'EDGE_TLS=',
        'EDGE_HEALTH_PATH=',
        'EDGE_WEBSOCKET=',
    )
    for key in required_keys:
        assert key in kaori
        assert key in n8n

    assert 'EDGE_UPSTREAM=kaori-web' in kaori
    assert 'EDGE_UPSTREAM_PORT=5000' in kaori
    assert 'EDGE_HEALTH_PATH=/health/ready' in kaori

    assert 'EDGE_UPSTREAM=n8n' in n8n
    assert 'EDGE_UPSTREAM_PORT=5678' in n8n
    assert 'EDGE_WEBSOCKET=true' in n8n
    assert 'example.com' in n8n


def test_shared_edge_prepare_preserves_legacy_certificate_lineage_without_binding_ports() -> None:
    prepare = _read(EDGE_PREPARE)

    assert 'kaori-vps-letsencrypt' in prepare
    assert 'edge-public' in prepare
    assert 'docker network create' in prepare
    assert 'LEGACY_KAORI_DEPLOY_ENV_FILE' in prepare
    assert 'kaori.env' in prepare

    for forbidden in ('up -d nginx', 'up -d certbot', '80:8080', '443:8443'):
        assert forbidden not in prepare


def test_shared_edge_apply_has_fail_closed_cutover_and_rollback() -> None:
    apply = _read(EDGE_APPLY)

    assert 'com.docker.compose.service=nginx' in apply
    assert 'com.docker.compose.service=certbot' in apply
    assert 'legacy_nginx' in apply
    assert 'legacy_certbot' in apply
    assert 'docker start' in apply
    assert 'docker stop' in apply
    assert 'rollback' in apply.lower()
    assert 'bash "$SCRIPT_DIR/verify.sh"' in apply
    assert 'docker compose' in apply


def test_shared_edge_verifier_checks_every_registered_tls_site() -> None:
    verify = _read(EDGE_VERIFY)

    for marker in (
        'getent ahostsv4',
        'HTTP redirect PASS',
        'TLS PASS',
        'HTTPS readiness PASS',
        'Unknown Host/SNI rejection PASS',
        'certbot renew --dry-run',
    ):
        assert marker in verify

    assert 'for site_file in' in verify
    assert 'EDGE_HEALTH_PATH' in verify


def test_shared_edge_runtime_reconciles_site_and_certificate_changes_without_docker_socket() -> None:
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


def test_shared_edge_has_a_dedicated_delivery_workflow() -> None:
    workflow = _read(EDGE_WORKFLOW)

    assert 'name: KAORI Shared Edge Deployment' in workflow
    assert 'workflow_dispatch:' in workflow
    assert 'kaori/edge-request' in workflow
    assert 'StrictHostKeyChecking=yes' in workflow
    assert 'deploy/edge' in workflow
    assert '/opt/shared-edge' in workflow
    assert 'prepare.sh' in workflow
    assert 'apply.sh' in workflow
    assert 'deploy/server/deploy.sh' not in workflow
