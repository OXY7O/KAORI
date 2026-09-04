from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIFY_SCRIPT = ROOT / 'deploy' / 'vps' / 'verify.sh'
APP_ENV_TEMPLATE = ROOT / 'deploy' / 'env' / 'app.env.example'


def test_internal_readiness_uses_trusted_host_without_widening_allowlist() -> None:
    verify_source = VERIFY_SCRIPT.read_text(encoding='utf-8')
    app_env_source = APP_ENV_TEMPLATE.read_text(encoding='utf-8')

    assert 'TRUSTED_HOSTS=kaori.cloud,localhost' in app_env_source
    assert 'TRUSTED_HOSTS=kaori.cloud,localhost,127.0.0.1' not in app_env_source
    assert (
        "urllib.request.Request('http://127.0.0.1:5000/health/ready', headers={'Host': 'localhost'})"
        in verify_source
    )
