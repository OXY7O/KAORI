import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTTP_TEMPLATE = ROOT / 'deploy/nginx/kaori-http.conf.template'
NGINX_TEMPLATE = ROOT / 'deploy/nginx/kaori.conf.template'
NGINX_ENTRYPOINT = ROOT / 'deploy/nginx/nginx-entrypoint.sh'
CERTBOT_ENTRYPOINT = ROOT / 'deploy/nginx/certbot-entrypoint.sh'
VERIFY = ROOT / 'deploy/nginx/verify-ingress.sh'
COMPOSE = ROOT / 'compose.production.yml'
VPS_COMPOSE = ROOT / 'deploy/vps/compose.vps.yml'
ENV_EXAMPLE = ROOT / '.env.production.example'
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


def test_production_web_is_compose_internal_only():
    text = _read(COMPOSE)
    web = _service_block(text, 'web', 'worker')

    assert 'expose:' in web
    assert '- "5000"' in web
    assert 'ports:' not in web
    assert 'KAORI_BIND_ADDRESS' not in web


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
    redis = _service_block(text, 'redis', 'nginx')
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
        'X-Forwarded-Port $server_port',
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


def test_environment_example_documents_compose_edge_contract():
    text = _read(ENV_EXAMPLE)

    for key in (
        'KAORI_PUBLIC_DOMAIN=',
        'KAORI_PUBLIC_IP=',
        'KAORI_LETSENCRYPT_EMAIL=',
        'KAORI_NGINX_IMAGE=',
        'KAORI_CERTBOT_IMAGE=',
    ):
        assert key in text
    assert 'KAORI_BIND_ADDRESS=' not in text


def test_uat_delivery_copies_ingress_assets_to_release_directory():
    text = _read(UAT_WORKFLOW)

    assert 'scp "${scp_opts[@]}" -r deploy/nginx "$target:$remote_release/deploy/"' in text
    assert 'chmod 700 -- "$remote_release"/deploy/nginx/*.sh' in text
