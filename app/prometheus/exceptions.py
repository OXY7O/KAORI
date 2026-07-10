class PrometheusError(Exception):
    """Base exception for Prometheus integration."""


class PrometheusConnectionError(PrometheusError):
    """Raised when connection to Prometheus fails."""


class PrometheusAuthenticationError(PrometheusError):
    """Raised when Prometheus authentication fails."""


class PrometheusQueryError(PrometheusError):
    """Raised when Prometheus query execution fails."""
