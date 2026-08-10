from __future__ import annotations

from pathlib import Path

import pytest

TEST_ROOT = Path(__file__).resolve().parent
_MARKER_BY_BUCKET = {
    'contracts': pytest.mark.contract,
    'debug': pytest.mark.debug,
    'e2e': pytest.mark.e2e,
    'integration': pytest.mark.integration,
    'migrations': pytest.mark.migration,
    'rendering': pytest.mark.rendering,
    'security': pytest.mark.security,
    'unit': pytest.mark.unit,
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply one canonical purpose marker based on the test location."""
    for item in items:
        relative = Path(item.path).resolve().relative_to(TEST_ROOT)
        bucket = relative.parts[0]
        marker = _MARKER_BY_BUCKET.get(bucket, pytest.mark.functional)
        item.add_marker(marker)
