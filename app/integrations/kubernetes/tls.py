from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import urllib3.connection as urllib3_connection
import urllib3.util.ssl_ as urllib3_ssl


@contextmanager
def weak_tls_context(
    *,
    enabled: bool,
) -> Iterator[None]:
    if not enabled:
        yield
        return

    original_util_create_context = urllib3_ssl.create_urllib3_context
    original_connection_create_context = getattr(
        urllib3_connection,
        'create_urllib3_context',
        None,
    )

    def create_weak_tls_context(
        *args: Any,
        **kwargs: Any,
    ):
        kwargs['ciphers'] = 'DEFAULT:@SECLEVEL=0'

        return original_util_create_context(
            *args,
            **kwargs,
        )

    urllib3_ssl.create_urllib3_context = create_weak_tls_context

    if original_connection_create_context is not None:
        setattr(
            urllib3_connection,
            'create_urllib3_context',
            create_weak_tls_context,
        )

    try:
        yield
    finally:
        urllib3_ssl.create_urllib3_context = original_util_create_context

        if original_connection_create_context is not None:
            setattr(
                urllib3_connection,
                'create_urllib3_context',
                original_connection_create_context,
            )
