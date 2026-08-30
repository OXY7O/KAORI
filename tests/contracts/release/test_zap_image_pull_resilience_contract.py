from pathlib import Path

ZAP_SCRIPT = Path('.github/ci/run-zap-baseline.sh')
CI_COMPOSE = Path('.github/ci/compose.yml')
ZAP_IMAGE = 'ghcr.io/zaproxy/zaproxy:2.17.0'


def test_zap_image_pull_uses_bounded_retry_and_backoff() -> None:
    script = ZAP_SCRIPT.read_text(encoding='utf-8')

    assert f'ZAP_IMAGE="${{KAORI_ZAP_IMAGE:-{ZAP_IMAGE}}}"' in script
    assert 'ZAP_PULL_ATTEMPTS="${KAORI_ZAP_PULL_ATTEMPTS:-5}"' in script
    assert 'ZAP_PULL_BASE_DELAY_SECONDS="${KAORI_ZAP_PULL_BASE_DELAY_SECONDS:-5}"' in script
    assert 'docker pull "$ZAP_IMAGE"' in script
    assert 'delay_seconds=$((ZAP_PULL_BASE_DELAY_SECONDS * attempt))' in script
    assert 'sleep "$delay_seconds"' in script


def test_zap_execution_uses_cached_image_after_resilient_pull() -> None:
    script = ZAP_SCRIPT.read_text(encoding='utf-8')
    compose = CI_COMPOSE.read_text(encoding='utf-8')

    assert '--pull never zap' in script
    assert f'image: ${{KAORI_ZAP_IMAGE:-{ZAP_IMAGE}}}' in compose
