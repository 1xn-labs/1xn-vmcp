"""Service interfaces for pluggable components."""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class TokenInfo:
    """Normalized token information."""
    user_id: str
    username: str
    email: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    token: Optional[str] = None


class IJWTService(Protocol):
    """Interface for JWT authentication services."""

    def extract_token_info(self, token: str) -> dict:
        """Extract token information from JWT.

        Args:
            token: JWT token string

        Returns:
            Dictionary with token claims (user_id, username, email, client_id, client_name)

        Raises:
            ValueError: If token is invalid
        """
        ...

    def validate_token(self, token: str) -> bool:
        """Validate a JWT token.

        Args:
            token: JWT token string

        Returns:
            True if valid, False otherwise
        """
        ...


class IUserContext(Protocol):
    """Interface for user context services."""

    user_id: str
    username: str
    email: Optional[str]
    token: str
    vmcp_name: str

    def __init__(
        self,
        user_id: str,
        username: str,
        user_email: Optional[str],
        token: str,
        vmcp_name: str
    ):
        """Initialize user context."""
        ...


class IAnalyticsService(Protocol):
    """Interface for analytics services."""

    def track_event(
        self,
        event_name: str,
        user_id: str,
        properties: Optional[dict] = None
    ) -> None:
        """Track an analytics event."""
        ...

    def track_mcp_tool_call(
        self,
        user_id: str,
        tool_name: str,
        mcp_server: str,
        success: bool,
        properties: Optional[dict] = None
    ) -> None:
        """Track an MCP tool call."""
        ...
