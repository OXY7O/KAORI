from __future__ import annotations

import hashlib
import json
from typing import Any


def payload_fingerprint(payload: dict[str, Any] | None) -> str:
    serialized = json.dumps(payload or {}, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def build_deduplication_key(*parts: object, fingerprint: str | None = None) -> str:
    readable = ':'.join(str(part).strip().lower().replace(' ', '-') for part in parts if part is not None)
    digest_source = f'{readable}:{fingerprint or ""}'
    digest = hashlib.sha256(digest_source.encode('utf-8')).hexdigest()[:20]
    prefix = readable[:220].rstrip(':')
    return f'{prefix}:{digest}' if prefix else digest
