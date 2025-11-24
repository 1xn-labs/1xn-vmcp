"""Default OSS service implementations."""

from dataclasses import dataclass
from typing import Any, Optional

from vmcp.config import settings
from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class DummyJWTService:
    """Dummy JWT service for OSS (no real authentication)."""

    def extract_token_info(self, token: str) -> dict:
        """Extract dummy token info."""
        return {
            "user_id": "1",  # OSS always uses integer user_id=1 (the dummy user)
            "username": "local-user",
            "email": settings.dummy_user_email,
            "client_id": "local-client",
            "client_name": "Local Client"
        }

    def validate_token(self, token: str) -> bool:
        """Always valid in OSS mode."""
        return True


@dataclass
class DummyUserContext:
    """
    Dummy user context for OSS.

    This is a pure identity container - it does NOT create VMCPConfigManager.
    The VMCPConfigManager is created by VMCPSessionManager and attached externally.
    """

    user_id: str
    username: str
    email: Optional[str]
    token: str
    vmcp_name: str
    vmcp_config_manager: Optional[Any] = None
    vmcp_name_header: Optional[str] = None
    vmcp_username_header: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    agent_name: Optional[str] = None

    def __init__(
        self,
        user_id: str,
        username: Optional[str] = None,
        user_email: Optional[str] = None,
        token: Optional[str] = None,
        vmcp_name: Optional[str] = None
    ):
        self.user_id = user_id
        self.username = username or "local-user"
        self.email = user_email or settings.dummy_user_email
        self.token = token or settings.dummy_user_token
        self.vmcp_name = vmcp_name or "default"

        # Initialize attributes that will be set externally by VMCPServer/VMCPSessionManager
        self.vmcp_config_manager = None
        self.vmcp_name_header = None
        self.vmcp_username_header = None
        self.client_id = None
        self.client_name = None
        self.agent_name = None

        # Note: VMCPConfigManager is NOT created here.
        # It is created by VMCPSessionManager.create_manager() and attached by VMCPServer.
        logger.debug(f"[DummyUserContext] Created identity for user_id={user_id}, vmcp_name={vmcp_name}")


def ensure_dummy_user():
    """Ensure dummy user exists in database."""
    try:
        from vmcp.storage.database import SessionLocal
        from vmcp.storage.models import User

        db = SessionLocal()
        try:
            # Check if dummy user exists (id=1 is the default OSS user)
            user = db.query(User).filter(User.id == 1).first()
            if not user:
                # Create dummy user with id=1
                user = User(
                    username="local-user",
                    email=settings.dummy_user_email,
                    first_name="Local",
                    last_name="User"
                )
                db.add(user)
                db.commit()
                logger.info(f"✅ Created dummy user with id={user.id}")
            else:
                logger.info(f"✅ Dummy user exists with id={user.id}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"⚠️ Could not ensure dummy user: {e}")


class NoOpAnalyticsService:
    """No-op analytics service for OSS."""

    def track_event(
        self,
        event_name: str,
        user_id: str,
        properties: Optional[dict] = None
    ) -> None:
        """No-op tracking."""
        logger.debug(f"[OSS] Analytics disabled: {event_name}")

    def track_mcp_tool_call(
        self,
        user_id: str,
        tool_name: str,
        mcp_server: str,
        success: bool,
        properties: Optional[dict] = None
    ) -> None:
        """No-op MCP tool tracking."""
        logger.debug(f"[OSS] Analytics disabled: MCP tool call {tool_name}")


def register_oss_services():
    """Register default OSS service implementations."""
    from vmcp.core.services.registry import get_registry

    registry = get_registry()
    registry.register_jwt_service(service_class=DummyJWTService)
    registry.register_user_context(context_class=DummyUserContext)
    registry.register_analytics_service(service_class=NoOpAnalyticsService)

    logger.info("✅ OSS services registered")
