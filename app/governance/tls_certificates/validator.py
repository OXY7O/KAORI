"""Compatibility imports for the shared TLS validation layer.

New code must import from :mod:`app.kubernetes.secrets.tls`.
"""

from app.kubernetes.secrets.tls import (
    CertificatePairValidation,
    ParsedCertificate,
    decode_secret_data,
    find_uncovered_hosts,
    parse_certificate,
    validate_certificate_pair,
)

__all__ = [
    "CertificatePairValidation",
    "ParsedCertificate",
    "decode_secret_data",
    "find_uncovered_hosts",
    "parse_certificate",
    "validate_certificate_pair",
]
