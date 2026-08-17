class MetricsSourceError(Exception):
    """Base exception for Metrics Source integration."""


class MetricsSourceConnectionError(MetricsSourceError):
    """Raised when connection to Metrics Source fails."""


class MetricsSourceAuthenticationError(MetricsSourceError):
    """Raised when Metrics Source authentication fails."""


class MetricsQueryError(MetricsSourceError):
    """Raised when Metrics Source query execution fails."""
