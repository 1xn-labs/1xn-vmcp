"""Central service registry for pluggable components."""

from typing import Callable, Optional, Type

from vmcp.core.services.interfaces import IAnalyticsService, IJWTService, IUserContext
from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class ServiceRegistry:
    """Central registry for pluggable services."""

    def __init__(self):
        self._jwt_service_class: Optional[Type[IJWTService]] = None
        self._user_context_class: Optional[Type[IUserContext]] = None
        self._analytics_service_class: Optional[Type[IAnalyticsService]] = None
        self._jwt_service_factory: Optional[Callable[[], IJWTService]] = None
        self._analytics_service_factory: Optional[Callable[[], IAnalyticsService]] = None

    # JWT Service
    def register_jwt_service(
        self,
        service_class: Optional[Type[IJWTService]] = None,
        factory: Optional[Callable[[], IJWTService]] = None
    ) -> None:
        """Register JWT service implementation."""
        if factory:
            self._jwt_service_factory = factory
            logger.info(f"📝 Registered JWT service factory: {factory.__name__}")
        elif service_class:
            self._jwt_service_class = service_class
            logger.info(f"📝 Registered JWT service: {service_class.__name__}")
        else:
            raise ValueError("Must provide either service_class or factory")

    def get_jwt_service(self) -> IJWTService:
        """Get JWT service instance."""
        if self._jwt_service_factory:
            return self._jwt_service_factory()
        if self._jwt_service_class:
            return self._jwt_service_class()
        raise RuntimeError("No JWT service registered")

    # User Context
    def register_user_context(self, context_class: Type[IUserContext]) -> None:
        """Register user context implementation."""
        self._user_context_class = context_class
        logger.info(f"📝 Registered user context: {context_class.__name__}")

    def get_user_context_class(self) -> Type[IUserContext]:
        """Get user context class."""
        if not self._user_context_class:
            raise RuntimeError("No user context registered")
        return self._user_context_class

    # Analytics Service
    def register_analytics_service(
        self,
        service_class: Optional[Type[IAnalyticsService]] = None,
        factory: Optional[Callable[[], IAnalyticsService]] = None
    ) -> None:
        """Register analytics service implementation."""
        if factory:
            self._analytics_service_factory = factory
            logger.info(f"📝 Registered analytics service factory: {factory.__name__}")
        elif service_class:
            self._analytics_service_class = service_class
            logger.info(f"📝 Registered analytics service: {service_class.__name__}")
        else:
            raise ValueError("Must provide either service_class or factory")

    def get_analytics_service(self) -> IAnalyticsService:
        """Get analytics service instance."""
        if self._analytics_service_factory:
            return self._analytics_service_factory()
        if self._analytics_service_class:
            return self._analytics_service_class()
        raise RuntimeError("No analytics service registered")


# Global registry instance
_registry = ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """Get the global service registry."""
    return _registry


# Convenience functions
def get_jwt_service() -> IJWTService:
    """Get JWT service from registry."""
    return _registry.get_jwt_service()


def get_user_context_class() -> Type[IUserContext]:
    """Get user context class from registry."""
    return _registry.get_user_context_class()


def get_analytics_service() -> IAnalyticsService:
    """Get analytics service from registry."""
    return _registry.get_analytics_service()
