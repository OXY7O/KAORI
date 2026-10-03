from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


_RUNTIME_PREFIXES = ('docker-pullable://', 'containerd://', 'cri-o://', 'docker://')


@dataclass(frozen=True, slots=True)
class ParsedImageReference:
    raw: str
    registry_host: str | None
    repository_path: str | None
    tag: str | None
    digest: str | None


def _strip_runtime_prefix(value: str) -> str:
    text = value.strip()
    for prefix in _RUNTIME_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _registry_host_and_path(value: str) -> tuple[str | None, str | None]:
    text = value.strip().lstrip('/')
    if not text:
        return None, None
    parts = text.split('/')
    first = parts[0].lower()
    if len(parts) > 1 and ('.' in first or ':' in first or first == 'localhost'):
        return first, '/'.join(parts[1:]) or None
    return None, text


def parse_image_reference(value: str | None) -> ParsedImageReference:
    raw = str(value or '').strip()
    text = _strip_runtime_prefix(raw)
    if not text:
        return ParsedImageReference(raw=raw, registry_host=None, repository_path=None, tag=None, digest=None)

    digest = None
    if '@' in text:
        text, digest_part = text.rsplit('@', 1)
        digest = digest_part.strip() or None
    elif text.startswith('sha256:'):
        return ParsedImageReference(raw=raw, registry_host=None, repository_path=None, tag=None, digest=text)

    registry_host, repository_and_tag = _registry_host_and_path(text)
    tag = None
    repository_path = repository_and_tag
    if repository_and_tag:
        last_slash = repository_and_tag.rfind('/')
        last_colon = repository_and_tag.rfind(':')
        if last_colon > last_slash:
            repository_path = repository_and_tag[:last_colon] or None
            tag = repository_and_tag[last_colon + 1 :] or None

    return ParsedImageReference(
        raw=raw,
        registry_host=registry_host,
        repository_path=repository_path.lower() if repository_path else None,
        tag=tag,
        digest=digest.lower() if digest else None,
    )


def normalize_registry_host(value: str | None) -> str | None:
    text = str(value or '').strip()
    if not text:
        return None
    candidate = text if '://' in text else f'//{text}'
    parsed = urlparse(candidate)
    host = parsed.netloc or parsed.path.split('/', 1)[0]
    return host.strip().lower() or None
