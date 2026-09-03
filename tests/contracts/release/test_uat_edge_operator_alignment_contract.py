from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-uat-vps.yml'
NGINX_README = ROOT / 'deploy' / 'nginx' / 'README.md'


def test_uat_workflow_forwards_letsencrypt_email_from_reviewed_repository_variable() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'KAORI_LETSENCRYPT_EMAIL: ${{ vars.KAORI_LETSENCRYPT_EMAIL }}' in workflow
    assert ': "${KAORI_LETSENCRYPT_EMAIL:?Missing KAORI_LETSENCRYPT_EMAIL variable}"' in workflow
    assert 'letsencrypt_email=' in workflow
    assert 'export KAORI_LETSENCRYPT_EMAIL="$letsencrypt_email"' in workflow


def test_nginx_runbook_describes_compose_managed_edge_not_retired_host_ingress() -> None:
    readme = NGINX_README.read_text(encoding='utf-8')

    required = (
        'Compose-managed Nginx',
        'Certbot',
        'web:5000',
        '/etc/kaori/deploy.env',
        'KAORI_NGINX_IMAGE',
        'KAORI_CERTBOT_IMAGE',
        'https://kaori.cloud',
        'verify-ingress.sh',
    )
    for marker in required:
        assert marker in readme

    assert 'Host Nginx' not in readme
    assert 'certbot.timer' not in readme
    assert 'bootstrap-ingress.sh' not in readme
    assert '127.0.0.1:5000' not in readme
