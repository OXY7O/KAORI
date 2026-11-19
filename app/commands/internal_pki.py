"""Operator-only, non-HTTP internal PKI metadata ingestion.

Does not execute kubeadm or read a private key; no arbitrary source execution.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

from app.kubernetes.governance.internal_certificates.evidence_import import (
    MAX_MANIFEST_BYTES,
    PKIEvidenceValidationError,
    import_attested_pki_metadata,
)
from app.kubernetes.governance.internal_certificates.kubeadm_adapter import (
    prepare_kubeadm_metadata_manifest,
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


@click.command(
    'prepare-internal-pki',
    short_help='Prepare a reviewed kubeadm v1.36.4 report as safe, metadata-only KAORI evidence.',
)
@click.option('--input-file', type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@click.option('--output-file', type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.option('--cluster-id', required=True, help='Registered KAORI cluster UUID, not a Kubernetes context name.')
@click.option('--node-name', required=True, help='Exact source control-plane node name.')
@click.option('--source-version', required=True, help='Source-local kubeadm version, currently v1.36.4.')
@click.option('--collected-at', required=True, help='UTC ISO 8601 time captured with the source report.')
@click.option('--reference', required=True, help='Approved operator evidence/change reference.')
@click.option('--coverage-state', type=click.Choice(('partial', 'complete')), default='partial', show_default=True)
@with_appcontext
def prepare_internal_pki(
    input_file: Path,
    output_file: Path,
    cluster_id: str,
    node_name: str,
    source_version: str,
    collected_at: str,
    reference: str,
    coverage_state: str,
) -> None:
    """Prepare a human-reviewable manifest outside Git without committing DB rows."""
    repository = Path(__file__).resolve().parents[2]
    destination = output_file.expanduser().resolve()
    if destination.is_relative_to(repository):
        raise click.ClickException('PKI metadata evidence must be written outside the repository.')

    try:
        with input_file.open('rb') as source:
            raw = source.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise PKIEvidenceValidationError('Kubeadm report exceeds the maximum accepted size.')
        report = json.loads(raw.decode('utf-8'))
        manifest = prepare_kubeadm_metadata_manifest(
            report,
            cluster_id=cluster_id,
            node_name=node_name,
            source_version=source_version,
            collected_at=collected_at,
            reference=reference,
            coverage_state=coverage_state,
        )
        encoded = json.dumps(manifest, indent=2, sort_keys=True).encode('utf-8') + b'\n'
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as target:
            target.write(encoded)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise click.ClickException('The kubeadm report is not valid UTF-8 JSON.') from exc
    except PKIEvidenceValidationError as exc:
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        raise click.ClickException('Cannot read the source or create the private metadata manifest.') from exc

    click.echo(
        'Internal PKI metadata prepared for operator review: '
        f'records={len(manifest["certificates"])}, source={source_version}, '
        f'coverage={coverage_state}. No database records were changed.'
    )
