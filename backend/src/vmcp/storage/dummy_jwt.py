"""
Dummy JWT service for vMCP OSS version.

Provides a stub JWT service that always returns the dummy user context.
"""

from typing import Optional, Dict, Any
from vmcp.config import settings


class DummyJWTService:
    """
    Dummy JWT service that bypasses authentication in OSS mode.
    
    Always returns the same dummy user information regardless of token.
    """
    
    def extract_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Extract token information (always returns dummy user in OSS).
        
        Returns normalized format compatible with both OSS and enterprise:
        - Uses "user_name" for OSS compatibility (normalized by token_info module)
        - Uses "email" for consistency (not "user_email")
        
        Args:
            token: JWT token (ignored in OSS mode)
            
        Returns:
            Dictionary with user information for the dummy user
        """
        return {
            "user_id": 1,
            "client_id": "local-client",
            "user_name": settings.dummy_user_id,  # Will be normalized to "username"
            "client_name": "Local Client",
            "email": settings.dummy_user_email,  # Consistent field name
            "is_dummy": True
        }
    
    def validate_token(self, token: str) -> bool:
        """
        Validate JWT token (always returns True in OSS).
        
        Args:
            token: JWT token (ignored in OSS mode)
            
        Returns:
            Always True in OSS mode
        """
        return True
    
    def create_token(self, user_id: int, **kwargs) -> str:
        """
        Create a JWT token (returns dummy token in OSS).
        
        Args:
            user_id: User ID (ignored in OSS mode)
            **kwargs: Additional claims (ignored in OSS mode)
            
        Returns:
            Dummy token string
        """
        return settings.dummy_user_token
