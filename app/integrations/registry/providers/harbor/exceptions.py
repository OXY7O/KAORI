from app.integrations.contracts.exceptions import IntegrationError


class HarborError(IntegrationError):
    """Base exception for Harbor integration failures."""


class HarborConnectionError(HarborError):
    """Raised when Harbor cannot be reached."""


class HarborResponseError(HarborError):
    """Raised when Harbor returns an unexpected response."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class HarborAuthError(HarborResponseError):
    """Raised when Harbor rejects the configured credentials."""
