import pytest

from app.resolver.operations import ResolverOperationalError, ResolverReadiness


def test_readiness_contract_is_immutable():
    readiness = ResolverReadiness(True, (), True, True, False, 0, 1)
    with pytest.raises(Exception):
        readiness.ready = False


def test_operational_error_is_explicit():
    with pytest.raises(ResolverOperationalError):
        raise ResolverOperationalError('blocked')
