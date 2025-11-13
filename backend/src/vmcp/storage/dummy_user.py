"""
Dummy user management for vMCP OSS version.

Creates and manages a single local user to maintain API consistency
while removing authentication complexity.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from vmcp.storage.models import User
from vmcp.config import settings

logger = logging.getLogger(__name__)


def get_or_create_dummy_user(db: Session) -> User:
    """
    Get or create the dummy user for local development.

    Args:
        db: Database session

    Returns:
        The dummy user instance
    """
    # Try to get existing dummy user
    user = db.query(User).filter(User.id == 1).first()

    if user is None:
        logger.info("Creating dummy user for local mode...")
        user = User(
            id=1,
            username=settings.dummy_user_id,
            email=settings.dummy_user_email,
            first_name="Local",
            last_name="User"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Dummy user created: {user.email}")
    else:
        logger.debug(f"Using existing dummy user: {user.email}")

    return user


def get_dummy_user_context() -> dict:
    """
    Get the dummy user context for dependency injection.

    Returns:
        Dictionary with user_id, user_email, and token
    """
    return {
        "user_id": 1,
        "user_email": settings.dummy_user_email,
        "username": settings.dummy_user_id,
        "token": settings.dummy_user_token,
        "is_dummy": True
    }


class UserContext:
    """
    User context for API dependencies.

    In OSS mode, this always represents the dummy local user.
    """

    def __init__(self, user_id: int = 1, user_email: str = None, username: str = None, token: str = None, vmcp_name: str = None):
        self.user_id = user_id
        self.user_email = user_email or settings.dummy_user_email
        self.username = username or settings.dummy_user_id
        self.token = token or settings.dummy_user_token
        self.is_dummy = True
        self.vmcp_name = vmcp_name
        
        # Add missing attributes for OSS compatibility with main application
        self.client_id = "oss-client"
        self.user_name = self.username  # Alias for compatibility
        self.client_name = "OSS Client"
        self.agent_name = "oss-agent"
        self.vmcp_name_header = vmcp_name
        self.vmcp_username_header = None
        
        # Initialize managers for OSS compatibility
        self._init_managers()

    def _init_managers(self):
        """Initialize vmcp_config_manager for OSS compatibility"""
        try:
            from vmcp.vmcps.vmcp_config_manger import VMCPConfigManager
            from vmcp.storage.base import StorageBase
            
            # Initialize vmcp_config_manager based on vmcp_name (similar to main application)
            if self.vmcp_name and self.vmcp_name != "vmcp" and self.vmcp_name != "unknown":
                # Create storage instance to find the actual vmcp_id
                storage = StorageBase(user_id=self.user_id)
                vmcp_id = storage.find_vmcp_name(self.vmcp_name)
                if vmcp_id:
                    self.vmcp_config_manager = VMCPConfigManager(self.user_id, vmcp_id)
                    logger.info(f"VMCP Config manager set: {vmcp_id}")
                else:
                    logger.warning(f"vMCP not found: {self.vmcp_name}")
                    self.vmcp_config_manager = None
            else:
                self.vmcp_config_manager = None
        except ImportError as e:
            # If VMCPConfigManager is not available, set to None
            self.vmcp_config_manager = None

    def __repr__(self):
        return f"<UserContext(user_id={self.user_id}, email='{self.user_email}')>"


def ensure_dummy_user():
    """
    Ensure the dummy user exists in the database.

    This is called on startup to initialize the database with the default user.
    """
    from vmcp.storage.database import SessionLocal

    db = SessionLocal()
    try:
        get_or_create_dummy_user(db)
    except Exception as e:
        logger.error(f"Failed to create dummy user: {e}")
        db.rollback()
    finally:
        db.close()


def get_user_context() -> UserContext:
    """
    Dependency for getting user context in FastAPI endpoints.

    Returns:
        UserContext instance for the dummy user
    """
    return UserContext()
