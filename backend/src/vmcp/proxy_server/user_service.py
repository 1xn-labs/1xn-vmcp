"""
User context service abstraction for proxy server.

This module provides a default UserContext (DummyUserContext for OSS).
Enterprise implementations should configure the UserContext before importing proxy_server.
"""

from vmcp.storage.dummy_user import UserContext as DummyUserContext
from vmcp.storage.dummy_user import ensure_dummy_user as dummy_ensure_dummy_user

# Default to dummy UserContext (OSS mode)
# Enterprise should configure this before importing proxy_server
UserContext = DummyUserContext
ensure_dummy_user = dummy_ensure_dummy_user

# Export for isinstance checks if needed
__all__ = ['UserContext', 'DummyUserContext', 'ensure_dummy_user', 'configure_user_context']

def configure_user_context(user_context_class, ensure_user_func=None):
    """
    Configure the UserContext class and ensure_user function to use.

    This should be called by enterprise entry points before importing proxy_server.

    Args:
        user_context_class: The UserContext class to use (must be compatible with DummyUserContext interface)
        ensure_user_func: Optional function to ensure user exists (for lifespan initialization)
    """
    global UserContext, ensure_dummy_user
    UserContext = user_context_class
    if ensure_user_func is not None:
        ensure_dummy_user = ensure_user_func

def is_dummy_user_context(user_context_instance):
    """
    Check if a user context instance is the dummy user context.

    Args:
        user_context_instance: An instance of UserContext

    Returns:
        bool: True if it's a dummy user context, False otherwise
    """
    return isinstance(user_context_instance, DummyUserContext)

