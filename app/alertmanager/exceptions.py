class AlertmanagerError(Exception):
    """Base exception for Alertmanager integration errors."""


class AlertmanagerConnectionError(AlertmanagerError):
    """Raised when Alertmanager cannot be reached."""


class AlertmanagerAuthError(AlertmanagerError):
    """Raised when Alertmanager authentication fails."""


class AlertmanagerResponseError(AlertmanagerError):
    """Raised when Alertmanager returns an invalid or unexpected response."""
