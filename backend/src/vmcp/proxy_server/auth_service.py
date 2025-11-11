"""
Authentication service abstraction for proxy server.

This module provides a default JWT service (DummyJWTService for OSS).
Enterprise implementations should configure the JWT service before importing proxy_server.
"""

from vmcp.proxy_server.token_info import TokenInfo, normalize_token_info
from vmcp.storage.dummy_jwt import DummyJWTService

# Default to dummy JWT service (OSS mode)
# Enterprise should configure this before importing proxy_server
JWTService = DummyJWTService

# Export for isinstance checks if needed
__all__ = ['JWTService', 'DummyJWTService', 'configure_jwt_service', 'get_normalized_token_info', 'TokenInfo']

def configure_jwt_service(service_class):
    """
    Configure the JWT service to use.
    
    This should be called by enterprise entry points before importing proxy_server.
    
    Args:
        service_class: The JWT service class to use (must have extract_token_info method)
    """
    global JWTService
    JWTService = service_class

def is_dummy_service(service_instance):
    """
    Check if a service instance is the dummy service.
    
    Args:
        service_instance: An instance of JWTService
        
    Returns:
        bool: True if it's a dummy service, False otherwise
    """
    return isinstance(service_instance, DummyJWTService)


def get_normalized_token_info(jwt_service, token: str) -> TokenInfo:
    """
    Get normalized token info from JWT service.
    
    This is a convenience function that extracts and normalizes token info,
    making it easy to work with tokens from both OSS and enterprise implementations.
    
    Args:
        jwt_service: Instance of JWTService
        token: JWT token string
        
    Returns:
        Normalized TokenInfo object
        
    Raises:
        ValueError: If token is invalid or missing required fields
    """
    raw_info = jwt_service.extract_token_info(token)
    normalized = normalize_token_info(raw_info, token)
    
    if normalized is None:
        raise ValueError(f"Invalid or incomplete token info: {raw_info}")
    
    return normalized

