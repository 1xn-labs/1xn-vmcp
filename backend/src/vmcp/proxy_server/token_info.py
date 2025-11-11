"""
Token information normalization for proxy server.

Provides a standardized TokenInfo structure that works with both OSS and enterprise tokens.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TokenInfo:
    """
    Normalized token information structure.

    This standardizes token info from both OSS (dummy) and enterprise JWT services,
    so proxy_server code can work with a consistent interface.
    """
    user_id: int
    username: str
    email: str
    token: Optional[str] = None

    # OSS-specific fields (may be None for enterprise tokens)
    client_id: Optional[str] = None
    client_name: Optional[str] = None

    # Additional metadata
    is_dummy: bool = False
    raw_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for compatibility"""
        result = {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
        }
        if self.client_id:
            result["client_id"] = self.client_id
        if self.client_name:
            result["client_name"] = self.client_name
        if self.token:
            result["token"] = self.token
        if self.is_dummy:
            result["is_dummy"] = self.is_dummy
        return result


def normalize_token_info(raw_token_info: Optional[Dict[str, Any]], token: Optional[str] = None) -> Optional[TokenInfo]:
    """
    Normalize token info from JWT service to standard TokenInfo format.

    This handles differences between OSS (dummy) and enterprise token formats:
    - OSS uses: user_name, user_email
    - Enterprise uses: username, email

    Args:
        raw_token_info: Raw token info dict from JWT service
        token: Optional token string for reference

    Returns:
        Normalized TokenInfo object, or None if invalid
    """
    if not raw_token_info:
        return None

    # Extract user_id (must be present)
    user_id = raw_token_info.get("user_id")
    if user_id is None:
        return None

    # Convert user_id to int if needed
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None

    # Normalize username: handle both "user_name" (OSS) and "username" (enterprise)
    username = raw_token_info.get("user_name") or raw_token_info.get("username") or ""

    # Normalize email: handle both "user_email" (OSS) and "email" (enterprise)
    email = raw_token_info.get("user_email") or raw_token_info.get("email") or ""

    # Extract optional OSS-specific fields
    client_id = raw_token_info.get("client_id")
    client_name = raw_token_info.get("client_name")

    # Check if this is a dummy token
    is_dummy = raw_token_info.get("is_dummy", False)

    return TokenInfo(
        user_id=user_id,
        username=username,
        email=email,
        token=token,
        client_id=client_id,
        client_name=client_name,
        is_dummy=is_dummy,
        raw_info=raw_token_info
    )

