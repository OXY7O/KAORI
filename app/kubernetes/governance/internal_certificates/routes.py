from __future__ import annotations

from flask import render_template, request

from app.access.rbac.decorators import permission_required
from app.kubernetes.cluster.onboarding import has_registered_clusters
from app.kubernetes.governance.internal_certificates.service import get_internal_certificates_source_page


@permission_required('governance.view')
@permission_required('clusters.view')
@permission_required('internal_certificates.view')
def internal_certificates_index():
    """Read-only, committed cluster source assessment; never contact a PKI provider."""
    registered_clusters = has_registered_clusters()
    payload = get_internal_certificates_source_page(request.args) if registered_clusters is True else None
    return render_template(
        'kubernetes/governance/internal_certificates/index.html',
        payload=payload,
        source_unavailable=registered_clusters is None,
    )
