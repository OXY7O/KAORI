from __future__ import annotations

from flask import render_template, request

from app.access.rbac.decorators import permission_required
from app.kubernetes.cluster.onboarding import has_registered_clusters
from app.kubernetes.governance.internal_certificates.readiness import check_internal_pki_schema_readiness
from app.kubernetes.governance.internal_certificates.service import (
    enrich_internal_pki_source_states,
    get_internal_certificate_inventory_page,
    get_internal_certificates_source_page,
)


@permission_required('governance.view')
@permission_required('clusters.view')
@permission_required('internal_certificates.view')
def internal_certificates_index():
    """Read-only, committed cluster source assessment; never contact a PKI provider."""
    active_tab = request.args.get('evidence_tab', 'sources')
    if active_tab not in {'sources', 'certificates'}:
        active_tab = 'sources'
    registered_clusters = has_registered_clusters()
    payload = get_internal_certificates_source_page(request.args) if registered_clusters is True else None
    schema_readiness = check_internal_pki_schema_readiness() if payload is not None else None
    inventory = None
    if payload is not None and schema_readiness is not None and schema_readiness.ready:
        enrich_internal_pki_source_states(payload)
        inventory = get_internal_certificate_inventory_page(request.args)

    return render_template(
        'kubernetes/governance/internal_certificates/index.html',
        payload=payload,
        inventory=inventory,
        schema_readiness=schema_readiness,
        active_tab=active_tab,
        source_unavailable=registered_clusters is None,
    )
