from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
README = ROOT / 'deploy/vps/README.md'


def test_vps_runbook_explains_local_and_production_environment_authority() -> None:
    source = README.read_text(encoding='utf-8')

    for token in (
        '.env.example',
        '`.env`',
        '/etc/kaori/app.env',
        '/etc/kaori/secrets.env',
        '/etc/kaori/deploy.env',
        '/var/lib/kaori/deploy-state/release.env',
        'deploy/env/app.env.example',
        'deploy/env/secrets.env.example',
        'deploy/env/deploy.env.example',
    ):
        assert token in source

    for stale_claim in (
        'The real application environment exists only on the VPS at `/etc/kaori/.env.production`',
        '`/etc/kaori/.env.production` is **long-lived operator configuration**',
        'KAORI web stays on `127.0.0.1:5000`',
        'KAORI_ENV_FILE=/etc/kaori/.env.production',
    ):
        assert stale_claim not in source


def test_vps_runbook_keeps_legacy_monolith_migration_only() -> None:
    source = README.read_text(encoding='utf-8')

    assert 'Legacy `.env.production` migration' in source
    assert 'Do not create a new `/etc/kaori/.env.production`' in source
    assert 'retire it only after a governed split-environment deployment passes' in source
