"""
Progressive Discovery Router for vMCP

Provides API endpoints for managing progressive discovery feature.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from vmcp.storage.dummy_user import UserContext, get_user_context
from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/vmcps/{vmcp_id}/progressive-discovery", tags=["Progressive Discovery"])


class ProgressiveDiscoveryStatusResponse(BaseModel):
    """Response model for progressive discovery status."""
    enabled: bool


@router.post("/enable", response_model=dict)
async def enable_progressive_discovery(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Enable progressive discovery for a vMCP.
    
    Persists the enabled state in vMCP metadata.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
        
        vmcp_config_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        vmcp_config = vmcp_config_manager.load_vmcp_config()
        
        if not vmcp_config:
            raise HTTPException(
                status_code=404,
                detail=f"vMCP not found: {vmcp_id}"
            )
        
        # Check if already enabled
        metadata = getattr(vmcp_config, 'metadata', {}) or {}
        if isinstance(metadata, dict) and metadata.get('progressive_discovery_enabled') is True:
            return {
                "success": True,
                "message": "Progressive discovery already enabled"
            }
        
        logger.info(f"Enabling progressive discovery for vMCP: {vmcp_id}")
        
        # Update metadata to include progressive_discovery_enabled flag
        if not isinstance(metadata, dict):
            metadata = {}
        metadata['progressive_discovery_enabled'] = True
        
        # Update the config with new metadata
        vmcp_config_manager.update_vmcp_config(
            vmcp_id=vmcp_id,
            metadata=metadata
        )
        logger.info(f"Persisted progressive discovery enabled state for vMCP {vmcp_id}")
        
        return {
            "success": True,
            "message": "Progressive discovery enabled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling progressive discovery for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error enabling progressive discovery: {str(e)}"
        )


@router.post("/disable", response_model=dict)
async def disable_progressive_discovery(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Disable progressive discovery for a vMCP.
    
    Persists the disabled state in vMCP metadata.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
        
        vmcp_config_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        vmcp_config = vmcp_config_manager.load_vmcp_config()
        
        if not vmcp_config:
            raise HTTPException(
                status_code=404,
                detail=f"vMCP not found: {vmcp_id}"
            )
        
        # Check if already disabled
        metadata = getattr(vmcp_config, 'metadata', {}) or {}
        if isinstance(metadata, dict) and metadata.get('progressive_discovery_enabled') is not True:
            return {
                "success": True,
                "message": "Progressive discovery already disabled"
            }
        
        logger.info(f"Disabling progressive discovery for vMCP: {vmcp_id}")
        
        # Update metadata to mark progressive discovery as disabled
        if not isinstance(metadata, dict):
            metadata = {}
        metadata['progressive_discovery_enabled'] = False
        
        # Update the config with new metadata
        vmcp_config_manager.update_vmcp_config(
            vmcp_id=vmcp_id,
            metadata=metadata
        )
        logger.info(f"Persisted progressive discovery disabled state for vMCP {vmcp_id}")
        
        return {
            "success": True,
            "message": "Progressive discovery disabled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling progressive discovery for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error disabling progressive discovery: {str(e)}"
        )


@router.get("/status", response_model=ProgressiveDiscoveryStatusResponse)
async def get_progressive_discovery_status(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Get progressive discovery status for a vMCP.
    
    Checks metadata flag for enabled state.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Progressive discovery status information
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
        from vmcp.vmcps.router_typesafe import get_cached_vmcp_config_manager
        
        # Use cached manager to avoid repeated initialization
        vmcp_config_manager = get_cached_vmcp_config_manager(user_context.user_id, vmcp_id)
        vmcp_config = vmcp_config_manager.load_vmcp_config()
        
        if not vmcp_config:
            raise HTTPException(
                status_code=404,
                detail=f"vMCP not found: {vmcp_id}"
            )
        
        # Check metadata for progressive_discovery_enabled flag
        metadata = getattr(vmcp_config, 'metadata', {}) or {}
        enabled = False
        if isinstance(metadata, dict):
            enabled = metadata.get('progressive_discovery_enabled', False) is True
        
        return ProgressiveDiscoveryStatusResponse(enabled=enabled)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting progressive discovery status for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting progressive discovery status: {str(e)}"
        )
