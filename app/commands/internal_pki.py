"""Operator-only, non-HTTP internal PKI metadata ingestion.

Does not execute kubeadm or read a private key; no arbitrary source execution.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

from app.kubernetes.governance.internal_certificates.evidence_import import (
    MAX_MANIFEST_BYTES,
    PKIEvidenceValidationError,
    import_attested_pki_metadata,
)


@click.command(
    'import-internal-pki',
    short_help='Commit strictly validated operator-attested Kubernetes PKI metadata.',
)
@click.option('--input-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@with_appcontext
def import_internal_pki(input_file: Path) -> None:
    """Run only against a reviewed database and approved control-plane source."""
    try:
        with input_file.open('rb') as source:
            raw = source.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise PKIEvidenceValidationError('PKI evidence exceeds the maximum accepted size.')
        document = json.loads(raw.decode('utf-8'))
        batch, created = import_attested_pki_metadata(document)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise click.ClickException('The PKI metadata manifest is not valid UTF-8 JSON.') from exc
    except PKIEvidenceValidationError as exc:
        raise click.ClickException(str(exc)) from exc
    except (OSError, SQLAlchemyError) as exc:
        raise click.ClickException('Unable to import PKI evidence. Verify schema and database readiness.') from exc

    click.echo(
        f'Internal PKI metadata {"committed" if created else "already committed"}: '
        f'batch={batch.id}, records={batch.record_count}, status=operator-attested'
    )
