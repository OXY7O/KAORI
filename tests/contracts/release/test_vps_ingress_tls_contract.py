import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTTP_TEMPLATE = ROOT / 'deploy/nginx/kaori-http.conf.template'
NGINX_TEMPLATE = ROOT / 'deploy/nginx/kaori.conf.template'
NGINX_ENTRYPOINT = ROOT / 'deploy/nginx/nginx-entrypoint.sh'
CERTBOT_ENTRYPOINT = ROOT / 'deploy/nginx/certbot-entrypoint.sh'
VERIFY = ROOT / 'deploy/nginx/verify-ingress.sh'
VPS_COMPOSE = ROOT / 'deploy/vps/compose.vps.yml'
LEGACY_ENV_EXAMPLE = ROOT / '.env.production.example'
APP_ENV_EXAMPLE = ROOT / 'deploy/env/app.env.example'
SECRETS_ENV_EXAMPLE = ROOT / 'deploy/env/secrets.env.example'
DEPLOY_ENV_EXAMPLE = ROOT / 'deploy/env/deploy.env.example'
DEPLOY_SCRIPT = ROOT / 'deploy/vps/deploy.sh'
RELEASE_STATE = ROOT / 'deploy/vps/release-state.sh'
UAT_WORKFLOW = ROOT / '.github/workflows/deploy-uat-vps.yml'


def _read(path: Path) -> str:
    assert path.is_file(), f'missing required ingress surface: {path.relative_to(ROOT)}'
    return path.read_text()


def _service_block(text: str, service: str, next_service: str | None = None) -> str:
    start = text.index(f'  {service}:')
    if next_service is None:
        return text[start:]
    end = text.index(f'  {next_service}:', start)
    return text[start:end]


def test_vps_overlay_makes_web_internal_only_and_replaces_runtime_env_files():
    text = _read(VPS_COMPOSE)
    web = _service_block(text, 'web', 'worker')

    assert 'ports: !reset []' in web
    assert 'expose:' in web
    assert '- "5000"' in web
    assert 'env_file: !override' in web
    assert '${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}' in web
    assert '${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}' in web
    assert '${KAORI_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}' in web


def test_vps_overlay_adds_immutable_nginx_and_certbot_without_docker_socket():
    text = _read(VPS_COMPOSE)

    assert 'KAORI_NGINX_IMAGE' in text
    assert 'KAORI_CERTBOT_IMAGE' in text
    assert 'KAORI_PUBLIC_DOMAIN' in text
    assert 'KAORI_LETSENCRYPT_EMAIL' in text
    assert '"80:8080"' in text
    assert '"443:8443"' in text
    assert 'kaori_vps_letsencrypt' in text
    assert 'kaori_vps_acme_webroot' in text
    assert '/var/run/docker.sock' not in text

    postgres = _service_block(text, 'postgres', 'redis')
    redis = _service_block(text, 'redis', 'validate')
    assert 'ports:' not in postgres
    assert 'ports:' not in redis


def test_nginx_templates_reject_unknown_hosts_and_proxy_only_to_compose_web():
    http_text = _read(HTTP_TEMPLATE)
    tls_text = _read(NGINX_TEMPLATE)

    assert 'listen 8080 default_server' in http_text
    assert 'server_name __KAORI_DOMAIN__' in http_text
    assert '/.well-known/acme-challenge/' in http_text
    assert 'proxy_pass' not in http_text

    assert 'listen 8080 default_server' in tls_text
    assert 'listen 8443 ssl default_server' in tls_text
    assert 'ssl_reject_handshake on' in tls_text
    assert 'server_name __KAORI_DOMAIN__' in tls_text
    assert 'proxy_pass http://web:5000' in tls_text
    assert '127.0.0.1:5000' not in tls_text
    assert 'ssl_protocols TLSv1.2 TLSv1.3' in tls_text
    assert 'Strict-Transport-Security' in tls_text
    assert 'Content-Security-Policy' not in tls_text

    for header in (
        'Host $host',
        'X-Real-IP $remote_addr',
        'X-Forwarded-For $proxy_add_x_forwarded_for',
        'X-Forwarded-Proto $scheme',
        'X-Forwarded-Host $host',
        'X-Forwarded-Port 443',
    ):
        assert f'proxy_set_header {header};' in tls_text


def test_container_edge_scripts_own_issuance_renewal_and_reload_without_host_mutation():
    nginx = _read(NGINX_ENTRYPOINT)
    certbot = _read(CERTBOT_ENTRYPOINT)

    assert 'nginx -t' in nginx
    assert 'nginx -s reload' in nginx
    assert 'fullchain.pem' in nginx
    assert 'privkey.pem' in nginx

    assert 'certbot certonly' in certbot
    assert '--webroot' in certbot
    assert 'certbot renew' in certbot
    assert 'KAORI_LETSENCRYPT_EMAIL' in certbot

    combined = f'{nginx}\n{certbot}'
    for forbidden in ('docker.sock', 'sudo ', 'systemctl', 'apt-get', 'usermod'):
        assert forbidden not in combined


def test_ingress_shell_surfaces_parse():
    for path, shell in (
        (NGINX_ENTRYPOINT, 'sh'),
        (CERTBOT_ENTRYPOINT, 'sh'),
        (VERIFY, 'bash'),
    ):
        result = subprocess.run(
            [shell, '-n', str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f'{path.relative_to(ROOT)}: {result.stderr}'


def test_verifier_checks_public_https_and_private_host_boundary():
    text = _read(VERIFY)

    assert 'https://$domain/health/ready' in text
    assert 'openssl s_client' in text
    assert 'subjectAltName' in text
    assert 'Strict-Transport-Security' in text
    assert 'ss -lnt' in text
    assert '5000' in text
    assert '5432' in text
    assert '6379' in text
    assert 'invalid.kaori.invalid' in text
    assert '🌐' in text
    assert '🔒' in text
    assert '🩺' in text
    assert '✅' in text


def test_runtime_environment_contract_is_split_by_authority():
    app = _read(APP_ENV_EXAMPLE)
    secrets = _read(SECRETS_ENV_EXAMPLE)
    deploy = _read(DEPLOY_ENV_EXAMPLE)
    legacy = _read(LEGACY_ENV_EXAMPLE)

    for key in ('APP_ENV=', 'KAORI_PUBLIC_BASE_URL=', 'TRUSTED_HOSTS=', 'PROXY_FIX_ENABLED='):
        assert key in app
    for forbidden in ('SECRET_KEY=', 'KAORI_NGINX_IMAGE=', 'KAORI_LETSENCRYPT_EMAIL='):
        assert forbidden not in app

    for key in ('SECRET_KEY=', 'INTEGRATION_CREDENTIAL_KEY=', 'POSTGRES_PASSWORD=', 'REDIS_PASSWORD='):
        assert key in secrets
    for forbidden in ('KAORI_NGINX_IMAGE=', 'KAORI_PUBLIC_DOMAIN=', 'APP_VERSION='):
        assert forbidden not in secrets

    for key in (
        'KAORI_POSTGRES_IMAGE=',
        'KAORI_REDIS_IMAGE=',
        'KAORI_NGINX_IMAGE=',
        'KAORI_CERTBOT_IMAGE=',
        'KAORI_PUBLIC_DOMAIN=kaori.cloud',
        'KAORI_PUBLIC_IP=62.171.187.206',
    ):
        assert key in deploy
    for forbidden in ('SECRET_KEY=', 'APP_VERSION=', 'APP_BUILD_SHA=', 'APP_BUILD_DATE='):
        assert forbidden not in deploy

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


def test_deploy_requires_compose_override_capability():
    deploy = _read(DEPLOY_SCRIPT)

    assert '2.24.4' in deploy
    assert 'docker compose version --short' in deploy


def test_uat_delivery_copies_ingress_assets_to_release_directory():
    text = _read(UAT_WORKFLOW)

    assert 'scp "${scp_opts[@]}" -r deploy/nginx "$target:$remote_release/deploy/"' in text
    assert 'chmod 700 -- "$remote_release"/deploy/vps/*.sh' in text
    assert 'chmod 755 -- "$remote_release"/deploy/nginx/*.sh' in text
