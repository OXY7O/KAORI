from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _normalize_storage_backend(value: str | None) -> str:
    backend = (value or 'local').strip().lower()
    return backend if backend in {'local', 's3'} else 'local'


def _resolve_path(value: str | None, default: Path) -> str:
    path = Path((value or str(default)).strip())
    return str(path if path.is_absolute() else BASE_DIR / path)


