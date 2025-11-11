"""Service registry and interfaces."""

from vmcp.core.services.interfaces import (
    IJWTService,
    IUserContext,
    IAnalyticsService,
    TokenInfo
)
from vmcp.core.services.registry import (
    get_registry,
    get_jwt_service,
    get_user_context_class,
    get_analytics_service
)
from vmcp.core.services.oss_providers import register_oss_services

__all__ = [
    'IJWTService',
    'IUserContext',
    'IAnalyticsService',
    'TokenInfo',
    'get_registry',
    'get_jwt_service',
    'get_user_context_class',
    'get_analytics_service',
    'register_oss_services'
]
