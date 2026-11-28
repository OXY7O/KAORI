"""Read bounded artifacts from an independently mounted authority directory.

Only internal callers supply fixed directories and allowlisted filenames.
No caller-controlled filesystem path, writable mount or symbolic link is accepted.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path


def _safe_file(info: os.stat_result, *, directory: bool = False) -> bool:
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    return expected_type(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022


def read_authority_file(directory: Path, name: str, *, max_bytes: int = 16384) -> bytes | None:
    """Read only a bounded, root-owned regular file on an actual read-only mount."""
    if (
        not isinstance(name, str)
        or re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,127}', name) is None
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= 16384
    ):
        return None
    directory_fd = None
    file_fd = None
    try:
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if not _safe_file(os.fstat(directory_fd), directory=True):
            return None
        if not os.fstatvfs(directory_fd).f_flag & os.ST_RDONLY:
            return None
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        info = os.fstat(file_fd)
        if not _safe_file(info) or not 0 < info.st_size <= max_bytes:
            return None
        if not os.fstatvfs(file_fd).f_flag & os.ST_RDONLY:
            return None
        with os.fdopen(file_fd, 'rb') as stream:
            file_fd = None
            content = stream.read(max_bytes + 1)
        return content if 0 < len(content) <= max_bytes else None
    except (OSError, AttributeError, ValueError):
        return None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
