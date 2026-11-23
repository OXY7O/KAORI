"""Definition-owned Kubernetes compatibility policy shared across domains (#5156).

The annual KAORI five-year policy is authoritative for Kubernetes API
visibility. No Integration provider or execution engine module is imported.
"""

from __future__ import annotations

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from app.definitions.integration_registry import integration_compatibility_document
from app.definitions.validation import require_int, require_list, require_mapping, require_str


def kubernetes_policy_identity() -> tuple[str, str]:
    """Return the validated annual identity and five-year window from one source."""
    document = integration_compatibility_document()
    policy = require_mapping(document.get('lifecycle_policy'), 'lifecycle_policy')
    key = require_str(policy, 'key', 'lifecycle_policy')
    year = require_int(policy, 'policy_year', 'lifecycle_policy')
    anchor = require_int(policy, 'anchor_year', 'lifecycle_policy')
    return key, f'{anchor}–{year}'


def kubernetes_api_lifecycle(version: str | None) -> str:
    """Use source-defined version bands only, without claiming runtime readiness."""
    document = integration_compatibility_document()
    products = require_list(document.get('products'), 'products')
    kubernetes = next(
        (
            require_mapping(product, 'products[kubernetes]')
            for product in products
            if isinstance(product, dict) and product.get('key') == 'kubernetes'
        ),
        None,
    )
    if kubernetes is None:
        raise ValueError('Canonical Kubernetes compatibility product is missing.')
    floor = Version(require_str(kubernetes, 'qualification_floor', 'products[kubernetes]'))
    try:
        current = Version(str(version or ''))
    except InvalidVersion:
        return 'unknown'
    if current < floor:
        return 'end_of_life'
    bands = require_list(document.get('qualifications'), 'qualifications')
    for entry in bands:
        qualification = require_mapping(entry, 'qualifications')
        if qualification.get('product') != 'kubernetes':
            continue
        constraint = require_str(qualification, 'version_constraint', 'qualifications[kubernetes]')
        if current not in SpecifierSet(constraint):
            continue
        status = require_str(qualification, 'support_level', 'qualifications[kubernetes]')
        return 'extended' if status == 'extended_supported' else status
    return 'unknown'
