from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
NGINX_TEMPLATE = ROOT / "deploy/nginx/kaori.conf.template"
BOOTSTRAP = ROOT / "deploy/nginx/bootstrap-ingress.sh"
VERIFY = ROOT / "deploy/nginx/verify-ingress.sh"
COMPOSE = ROOT / "compose.production.yml"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing required ingress surface: {path.relative_to(ROOT)}"
    return path.read_text()


def test_ingress_template_rejects_unknown_hosts_and_proxies_only_loopback():
    text = _read(NGINX_TEMPLATE)

    assert "listen 80 default_server" in text
    assert "listen 443 ssl default_server" in text
    assert "ssl_reject_handshake on" in text
    assert "server_name __KAORI_DOMAIN__" in text
    assert "proxy_pass http://127.0.0.1:5000" in text
    assert "ssl_protocols TLSv1.2 TLSv1.3" in text
    assert "Strict-Transport-Security" in text
    assert "Content-Security-Policy" not in text

    for header in (
        "Host $host",
        "X-Real-IP $remote_addr",
        "X-Forwarded-For $proxy_add_x_forwarded_for",
        "X-Forwarded-Proto $scheme",
        "X-Forwarded-Host $host",
        "X-Forwarded-Port $server_port",
    ):
        assert f"proxy_set_header {header};" in text


def test_bootstrap_is_root_owned_and_requires_dns_before_acme():
    text = _read(BOOTSTRAP)

    assert "EUID" in text
    assert "--domain" in text
    assert "--email" in text
    assert "getent ahostsv4" in text
    assert "ip -4 -o addr show scope global" in text
    assert "http://127.0.0.1:5000/health/ready" in text
    assert "certbot certonly" in text
    assert "--webroot" in text
    assert "certbot renew --dry-run" in text
    assert "nginx -t" in text
    assert "systemctl reload nginx" in text
    assert "sudoers" not in text.lower()
    assert "usermod" not in text


def test_verifier_checks_public_https_and_private_runtime_boundary():
    text = _read(VERIFY)

    assert "https://$domain/health/ready" in text
    assert "http://127.0.0.1:5000/health/ready" in text
    assert "openssl s_client" in text
    assert "subjectAltName" in text
    assert "Strict-Transport-Security" in text
    assert "ss -lnt" in text
    assert "5432" in text
    assert "6379" in text
    assert "invalid.kaori.invalid" in text
    assert "🌐" in text
    assert "🔒" in text
    assert "🩺" in text
    assert "✅" in text


def test_production_compose_keeps_web_on_loopback_and_state_ports_private():
    text = _read(COMPOSE)

    assert '"${KAORI_BIND_ADDRESS:-127.0.0.1}:${KAORI_PORT:-5000}:5000"' in text

    vps_compose = _read(ROOT / "deploy/vps/compose.vps.yml")
    postgres = vps_compose.split("  redis:", maxsplit=1)[0]
    redis = vps_compose.split("  redis:", maxsplit=1)[1].split("volumes:", maxsplit=1)[0]
    assert "ports:" not in postgres
    assert "ports:" not in redis
