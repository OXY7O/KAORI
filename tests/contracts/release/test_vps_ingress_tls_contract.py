import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDGE_ROOT = ROOT / 'example' / 'shared-edge'
EDGE_COMPOSE = EDGE_ROOT / 'compose.yml'
NGINX_ENTRYPOINT = EDGE_ROOT / 'nginx-entrypoint.sh'
CERTBOT_ENTRYPOINT = EDGE_ROOT / 'certbot-entrypoint.sh'
PREPARE = EDGE_ROOT / 'prepare.sh'
PUBLISH = EDGE_ROOT / 'publish-container.sh'
APPLY = EDGE_ROOT / 'apply.sh'
VERIFY = EDGE_ROOT / 'verify.sh'
KAORI_CUTOVER = EDGE_ROOT / 'kaori-cutover-example.sh'
SERVER_COMPOSE = ROOT / 'deploy' / 'server' / 'compose.server.yml'
LEGACY_ENV_EXAMPLE = ROOT / '.env.production.example'
APP_ENV_EXAMPLE = ROOT / 'deploy/env/app.env.example'
SECRETS_ENV_EXAMPLE = ROOT / 'deploy/env/secrets.env.example'
DEPLOY_ENV_EXAMPLE = ROOT / 'deploy/env/deploy.env.example'
EDGE_ENV_EXAMPLE = EDGE_ROOT / 'edge.env.example'
DEPLOY_SCRIPT = ROOT / 'deploy' / 'server' / 'deploy.sh'
RELEASE_STATE = ROOT / 'deploy' / 'server' / 'release-state.sh'
UAT_WORKFLOW = ROOT / '.github/workflows/deploy-staging-host.yml'


def _read(path: Path) -> str:
    assert path.is_file(), f'missing required ingress surface: {path.relative_to(ROOT)}'
    return path.read_text(encoding='utf-8')


def _service_block(text: str, service: str, next_service: str | None = None) -> str:
    start = text.index(f'  {service}:')
    if next_service is None:
        return text[start:]
    end = text.index(f'  {next_service}:', start)
    return text[start:end]


def test_server_overlay_keeps_web_internal_and_publication_agnostic():
    text = _read(SERVER_COMPOSE)
    web = _service_block(text, 'web', 'worker')

    assert 'ports: !reset []' in web
    assert 'expose:' in web
    assert '- "5000"' in web
    assert 'env_file: !override' in web
    assert '${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}' in web
    assert '${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}' in web
    assert '${KAORI_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}' in web
    assert 'edge-public' not in text
    assert 'edge_public' not in text
    assert '  nginx:' not in text
    assert '  certbot:' not in text


def test_standalone_edge_example_owns_immutable_nginx_and_certbot_without_docker_socket():
    text = _read(EDGE_COMPOSE)

    assert '${EDGE_NGINX_IMAGE:?' in text
    assert '${EDGE_CERTBOT_IMAGE:?' in text
    assert '"80:8080"' in text
    assert '"443:8443"' in text
    assert '${EDGE_CERTIFICATE_DIR:-/opt/shared-edge/state/letsencrypt}' in text
    assert '${EDGE_ACME_WEBROOT_DIR:-/opt/shared-edge/state/acme-webroot}' in text
    assert '${EDGE_SITES_DIR:-/opt/shared-edge/config/sites}' in text
    assert 'name: edge-public' in text
    assert 'external: true' in text
    assert '/var/run/docker.sock' not in text


def test_nginx_reconciler_rejects_unknown_hosts_and_proxies_registered_upstreams():
    nginx = _read(NGINX_ENTRYPOINT)

    assert 'listen 8080 default_server' in nginx
    assert 'listen 8443 ssl default_server' in nginx
    assert 'ssl_reject_handshake on' in nginx
    assert 'proxy_pass http://$EDGE_UPSTREAM:$EDGE_UPSTREAM_PORT' in nginx
    assert 'ssl_protocols TLSv1.2 TLSv1.3' in nginx
    assert 'Strict-Transport-Security' in nginx
    assert 'Content-Security-Policy' not in nginx
    assert 'EDGE_WEBSOCKET' in nginx

    for header in (
        'Host \\$host',
        'X-Real-IP \\$remote_addr',
        'X-Forwarded-For \\$proxy_add_x_forwarded_for',
        'X-Forwarded-Proto \\$scheme',
        'X-Forwarded-Host \\$host',
    ):
        assert f'proxy_set_header {header};' in nginx


def test_generic_edge_scripts_have_no_kaori_dependency():
    prepare = _read(PREPARE)
    publish = _read(PUBLISH)
    apply = _read(APPLY)

    assert 'docker network create edge-public' in prepare
    assert 'docker network connect --alias' in publish
    assert 'verify.sh' in apply

    combined = '\n'.join((prepare, publish, apply))
    for forbidden in ('/etc/kaori', 'kaori-production', 'kaori-vps-letsencrypt', 'KAORI_'):
        assert forbidden not in combined


def test_kaori_specific_cutover_is_isolated_to_explicit_example():
    source = _read(KAORI_CUTOVER)

    assert 'kaori-production' in source
    assert 'kaori-vps-letsencrypt' in source
    assert 'kaori.cloud' in source
    assert 'publish-container.sh' in source
    assert '--port 5000' in source
    assert 'rollback' in source.lower()


def test_edge_container_scripts_own_issuance_renewal_and_reload_without_host_mutation():
    nginx = _read(NGINX_ENTRYPOINT)
    certbot = _read(CERTBOT_ENTRYPOINT)

    assert 'nginx -t' in nginx
    assert 'nginx -s reload' in nginx
    assert 'fullchain.pem' in nginx
    assert 'privkey.pem' in nginx

    assert 'certbot certonly' in certbot
    assert '--webroot' in certbot
    assert 'certbot renew' in certbot
    assert 'EDGE_LETSENCRYPT_EMAIL' in certbot

    combined = f'{nginx}\n{certbot}'
    for forbidden in ('docker.sock', 'sudo ', 'systemctl', 'apt-get', 'usermod'):
        assert forbidden not in combined


def test_edge_shell_surfaces_parse():
    for path, shell in (
        (NGINX_ENTRYPOINT, 'sh'),
        (CERTBOT_ENTRYPOINT, 'sh'),
        (PREPARE, 'bash'),
        (PUBLISH, 'bash'),
        (APPLY, 'bash'),
        (VERIFY, 'bash'),
        (KAORI_CUTOVER, 'bash'),
    ):
        result = subprocess.run(
            [shell, '-n', str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f'{path.relative_to(ROOT)}: {result.stderr}'


def test_verifier_checks_every_public_site_and_host_boundary():
    text = _read(VERIFY)

    assert 'for site_file in "$EDGE_SITES_DIR"/*.env' in text
    assert 'EDGE_HEALTH_PATH' in text
    assert 'openssl s_client' in text
    assert 'subjectAltName' in text
    assert 'Strict-Transport-Security' in text
    assert 'invalid.shared-edge.invalid' in text
    assert 'certbot renew --dry-run' in text


def test_runtime_environment_contract_is_split_by_authority():
    app = _read(APP_ENV_EXAMPLE)
    secrets = _read(SECRETS_ENV_EXAMPLE)
    deploy = _read(DEPLOY_ENV_EXAMPLE)
    edge = _read(EDGE_ENV_EXAMPLE)
    legacy = _read(LEGACY_ENV_EXAMPLE)

    for key in ('APP_ENV=', 'KAORI_PUBLIC_BASE_URL=', 'TRUSTED_HOSTS=', 'PROXY_FIX_ENABLED='):
        assert key in app
    for forbidden in ('SECRET_KEY=', 'KAORI_NGINX_IMAGE=', 'KAORI_LETSENCRYPT_EMAIL='):
        assert forbidden not in app

    for key in ('SECRET_KEY=', 'INTEGRATION_CREDENTIAL_KEY=', 'POSTGRES_PASSWORD=', 'REDIS_PASSWORD='):
        assert key in secrets
    for forbidden in ('KAORI_NGINX_IMAGE=', 'KAORI_PUBLIC_DOMAIN=', 'APP_VERSION='):
        assert forbidden not in secrets

    for key in ('KAORI_POSTGRES_IMAGE=', 'KAORI_REDIS_IMAGE='):
        assert key in deploy
    for forbidden in (
        'KAORI_NGINX_IMAGE=',
        'KAORI_CERTBOT_IMAGE=',
        'KAORI_LETSENCRYPT_EMAIL=',
        'KAORI_PUBLIC_IP=',
        'KAORI_PUBLIC_DOMAIN=',
    ):
        assert forbidden not in deploy

    for key in ('EDGE_NGINX_IMAGE=', 'EDGE_CERTBOT_IMAGE=', 'EDGE_LETSENCRYPT_EMAIL=', 'EDGE_PUBLIC_IP='):
        assert key in edge
    assert '/opt/shared-edge/config/sites' in edge
    assert '/opt/shared-edge/state/letsencrypt' in edge

    assert 'deprecated' in legacy.lower()
    assert 'deploy/env/app.env.example' in legacy
    assert 'deploy/env/secrets.env.example' in legacy
    assert 'deploy/env/deploy.env.example' in legacy


def test_release_identity_is_generated_separately_from_persistent_configuration():
    deploy = _read(DEPLOY_SCRIPT)
    state = _read(RELEASE_STATE)

    assert '/etc/kaori/app.env' in deploy
    assert '/etc/kaori/secrets.env' in deploy
    assert '/etc/kaori/deploy.env' in deploy
    assert '/var/lib/kaori/deploy-state/release.env' in deploy
    assert 'candidate-release.env' in deploy
    for key in ('KAORI_IMAGE', 'APP_VERSION', 'APP_BUILD_SHA', 'APP_BUILD_DATE'):
        assert f'{key}=' in deploy
    assert 'mv -- "$candidate_release_env" "$active_release_env"' in deploy
    assert '/var/lib/kaori/deploy-state/release.env' in state


def test_application_delivery_does_not_ship_or_manage_public_edge():
    uat = _read(UAT_WORKFLOW)

    assert 'scp "${scp_opts[@]}" -r deploy/server' in uat
    assert 'deploy/nginx' not in uat
    assert 'deploy/edge' not in uat
    assert 'example/shared-edge' not in uat
    assert 'KAORI_LETSENCRYPT_EMAIL' not in uat
