"""Compatibility exports for the existing Vault KV v2 metadata callers."""

from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    KV2CollectionEvidence as KV2CollectionEvidence,
    KV2SecretEvidence as KV2SecretEvidence,
    KV2VersionEvidence as KV2VersionEvidence,
    MAX_DEPTH as MAX_DEPTH,
    MAX_LIST_ENTRIES as MAX_LIST_ENTRIES,
    MAX_SECRETS as MAX_SECRETS,
    MAX_VERSIONS_PER_SECRET as MAX_VERSIONS_PER_SECRET,
    _api_path as _api_path,
    _safe_metadata as _safe_metadata,
    _safe_timestamp as _safe_timestamp,
    _segments as _segments,
    _version_number as _version_number,
    collect_kv2_metadata as collect_kv2_metadata,
    parse_approved_kv2_mounts as parse_approved_kv2_mounts,
)
