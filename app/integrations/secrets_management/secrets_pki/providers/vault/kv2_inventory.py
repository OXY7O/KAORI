"""Compatibility exports for the existing Vault KV v2 metadata callers."""

from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    MAX_DEPTH as MAX_DEPTH,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    MAX_LIST_ENTRIES as MAX_LIST_ENTRIES,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    MAX_SECRETS as MAX_SECRETS,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    MAX_VERSIONS_PER_SECRET as MAX_VERSIONS_PER_SECRET,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    KV2CollectionEvidence as KV2CollectionEvidence,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    KV2SecretEvidence as KV2SecretEvidence,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    KV2VersionEvidence as KV2VersionEvidence,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    _api_path as _api_path,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    _safe_metadata as _safe_metadata,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    _safe_timestamp as _safe_timestamp,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    _segments as _segments,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    _version_number as _version_number,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    collect_kv2_metadata as collect_kv2_metadata,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    parse_approved_kv2_mounts as parse_approved_kv2_mounts,
)
