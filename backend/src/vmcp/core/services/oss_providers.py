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
    """Dummy user context for OSS."""

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

        # Initialize attributes that will be set later
        self.vmcp_config_manager = None
        self.vmcp_name_header = None
        self.vmcp_username_header = None
        self.client_id = None
        self.client_name = None
        self.agent_name = None

        # Initialize vmcp_config_manager
        try:
            from vmcp.storage.base import StorageBase
            from vmcp.vmcps.vmcp_config_manager.config_core import VMCPConfigManager

            # Convert user_id to integer for storage operations (OSS uses integer IDs)
            user_id_int = int(user_id) if isinstance(user_id, str) else user_id

            # If vmcp_name is provided, resolve it to UUID
            vmcp_id = None
            if self.vmcp_name:
                logger.info(f"🔍 DummyUserContext: Resolving vmcp_name '{self.vmcp_name}' to UUID for user '{user_id_int}'")
                storage = StorageBase(user_id=user_id_int)
                vmcp_id = storage.find_vmcp_name_in_private_registry(self.vmcp_name)
                if vmcp_id:
                    logger.info(f"✅ DummyUserContext: Resolved '{self.vmcp_name}' -> '{vmcp_id}'")
                else:
                    logger.warning(f"❌ DummyUserContext: Could not find vMCP UUID for name: {self.vmcp_name}")

            self.vmcp_config_manager = VMCPConfigManager(
                user_id=str(user_id),  # VMCPConfigManager expects string user_id
                vmcp_id=vmcp_id  # Pass resolved UUID
            )
        except Exception as e:
            logger.warning(f"Failed to initialize VMCPConfigManager: {e}")


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
