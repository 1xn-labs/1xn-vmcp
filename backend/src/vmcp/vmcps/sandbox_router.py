"""
Sandbox Router for vMCP

Provides API endpoints for managing per-vMCP sandbox environments.
"""

import os
import json
# import asyncio  # TERMINAL FEATURE DISABLED - only needed for terminal websocket
# import struct  # TERMINAL FEATURE DISABLED - only needed for terminal websocket
# import fcntl  # TERMINAL FEATURE DISABLED - only needed for terminal websocket
# import termios  # TERMINAL FEATURE DISABLED - only needed for terminal websocket
# import select  # TERMINAL FEATURE DISABLED - only needed for terminal websocket
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
# , WebSocket, WebSocketDisconnect, Query  # TERMINAL FEATURE DISABLED - only needed for terminal websocket
from pydantic import BaseModel

from vmcp.storage.dummy_user import UserContext, get_user_context
from vmcp.vmcps.sandbox_service import get_sandbox_service
# from vmcp.vmcps.terminal_session_manager import get_terminal_session_manager  # TERMINAL FEATURE DISABLED
from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/vmcps/{vmcp_id}/sandbox", tags=["Sandbox"])

class SandboxStatusResponse(BaseModel):
    """Response model for sandbox status."""
    enabled: bool
    path: str
    venv_exists: bool
    folder_exists: bool

class FileNode(BaseModel):
    """File node in the sandbox directory tree."""
    name: str
    path: str
    type: str  # 'file' or 'directory'
    children: Optional[List['FileNode']] = None
    size: Optional[int] = None
    modified: Optional[str] = None


class FileContentResponse(BaseModel):
    """Response model for file content."""
    content: str
    path: str
    size: int


# Allow recursive FileNode
FileNode.model_rebuild()


def _build_file_tree(directory: Path, base_path: Path) -> List[FileNode]:
    """
    Build a file tree structure from a directory.
    
    Args:
        directory: The directory to scan
        base_path: Base path for relative paths
        
    Returns:
        List of FileNode objects
    """
    nodes = []
    
    if not directory.exists() or not directory.is_dir():
        return nodes
    
    try:
        items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        
        for item in items:
            # Show all files and folders including hidden ones and .venv

            relative_path = item.relative_to(base_path)
            
            node = FileNode(
                name=item.name,
                path=str(relative_path).replace('\\', '/'),  # Normalize path separators
                type='directory' if item.is_dir() else 'file',
                size=item.stat().st_size if item.is_file() else None,
                modified=str(item.stat().st_mtime) if item.exists() else None
            )
            
            if item.is_dir():
                node.children = _build_file_tree(item, base_path)
            
            nodes.append(node)
    except PermissionError:
        logger.warning(f"Permission denied accessing {directory}")
    except Exception as e:
        logger.error(f"Error building file tree for {directory}: {e}")
    
    return nodes


@router.post("/attach", response_model=dict)
async def attach_sandbox(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Attach sandbox to vMCP (creates sandbox if doesn't exist).
    This is a prerequisite for creating Python tools.
    
    Creates sandbox directory, virtual environment, and sets sandbox_enabled=True.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Success message with sandbox details
    """
    return await enable_sandbox(vmcp_id, user_context)

@router.post("/enable", response_model=dict)
async def enable_sandbox(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Enable sandbox for a vMCP.
    
    If directory exists, just sets the flag to enabled.
    If directory doesn't exist, creates it with virtual environment.
    Persists the enabled state in vMCP metadata.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
        
        sandbox_service = get_sandbox_service()
        vmcp_config_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        vmcp_config = vmcp_config_manager.load_vmcp_config()
        
        # Check if already enabled
        if vmcp_config and sandbox_service.is_enabled(vmcp_id, vmcp_config):
            return {
                "success": True,
                "message": "Sandbox already enabled",
                "path": str(sandbox_service.get_sandbox_path(vmcp_id))
            }
        
        logger.info(f"Enabling sandbox for vMCP: {vmcp_id}")
        
        # Check if directory exists
        if sandbox_service.sandbox_exists(vmcp_id):
            # Directory exists, just ensure venv exists and packages are installed
            if not sandbox_service.venv_exists(vmcp_id):
                logger.info(f"Sandbox directory exists but venv missing, creating venv and installing packages for {vmcp_id}")
                # Create venv and install packages
                sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
                success = sandbox_service._setup_venv_and_packages(sandbox_path, vmcp_id)
                if not success:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to create virtual environment. Check logs for details."
                    )
            else:
                logger.info(f"Sandbox directory and venv already exist for {vmcp_id}, using existing")
                # Ensure config file exists
                sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
                config_path = sandbox_path / ".vmcp-config.json"
                if not config_path.exists():
                    sandbox_service._create_sandbox_config(sandbox_path, vmcp_id)
        else:
            # Directory doesn't exist, create full sandbox
            logger.info(f"Creating new sandbox for vMCP: {vmcp_id}")
            success = sandbox_service.create_sandbox(vmcp_id)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create sandbox. Check logs for details."
                )
        
        # Persist sandbox enabled state in vMCP metadata
        try:
            if vmcp_config:
                # Update metadata to include sandbox_enabled flag
                metadata = getattr(vmcp_config, 'metadata', {}) or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata['sandbox_enabled'] = True
                
                # Update the config with new metadata
                vmcp_config_manager.update_vmcp_config(
                    vmcp_id=vmcp_id,
                    metadata=metadata
                )
                logger.info(f"Persisted sandbox enabled state for vMCP {vmcp_id}")
        except Exception as e:
            logger.warning(f"Failed to persist sandbox state in metadata for {vmcp_id}: {e}")
            # Don't fail the request if metadata update fails
        
        return {
            "success": True,
            "message": "Sandbox enabled successfully",
            "path": str(sandbox_service.get_sandbox_path(vmcp_id))
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling sandbox for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error enabling sandbox: {str(e)}"
        )


@router.post("/disable", response_model=dict)
async def disable_sandbox(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Disable sandbox for a vMCP.
    
    Only sets the flag to disabled in metadata. Does not delete the directory.
    To delete the sandbox, use the delete endpoint.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
        
        sandbox_service = get_sandbox_service()
        vmcp_config_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        vmcp_config = vmcp_config_manager.load_vmcp_config()
        
        # Check if already disabled
        if vmcp_config and not sandbox_service.is_enabled(vmcp_id, vmcp_config):
            return {
                "success": True,
                "message": "Sandbox already disabled"
            }
        
        logger.info(f"Disabling sandbox for vMCP: {vmcp_id}")
        
        # Persist sandbox disabled state in vMCP metadata
        try:
            if vmcp_config:
                # Update metadata to mark sandbox as disabled
                metadata = getattr(vmcp_config, 'metadata', {}) or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata['sandbox_enabled'] = False
                
                # Update the config with new metadata
                vmcp_config_manager.update_vmcp_config(
                    vmcp_id=vmcp_id,
                    metadata=metadata
                )
                logger.info(f"Persisted sandbox disabled state for vMCP {vmcp_id}")
        except Exception as e:
            logger.warning(f"Failed to persist sandbox state in metadata for {vmcp_id}: {e}")
            # Don't fail the request if metadata update fails
        
        return {
            "success": True,
            "message": "Sandbox disabled successfully"
        }
    except Exception as e:
        logger.error(f"Error disabling sandbox for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error disabling sandbox: {str(e)}"
        )


@router.delete("/delete", response_model=dict)
async def delete_sandbox(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Delete the sandbox directory and set flag to disabled.
    
    This permanently deletes the sandbox directory and all its contents.
    Also sets sandbox_enabled to False in metadata.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
        
        # Add sandbox-runtime-py to sys.path to allow importing SandboxManager
        import sys
        from pathlib import Path
        
        # Calculate path to sandbox-runtime-py relative to this file
        # current file: backend/src/vmcp/vmcps/sandbox_router.py
        # target: backend/src/sandbox-runtime-py
        current_file = Path(__file__)
        # Go up 3 levels: vmcp/vmcps/ -> vmcp/ -> src/
        src_dir = current_file.parent.parent.parent
        sandbox_runtime_path = src_dir / "sandbox-runtime-py"
        
        if str(sandbox_runtime_path) not in sys.path:
            sys.path.insert(0, str(sandbox_runtime_path))
            
        from sandbox_runtime import SandboxManager
        
        sandbox_service = get_sandbox_service()
        vmcp_config_manager = VMCPConfigManager(user_context.user_id, vmcp_id)
        vmcp_config = vmcp_config_manager.load_vmcp_config()
        
        logger.info(f"Deleting sandbox for vMCP: {vmcp_id}")

        # Reset global sandbox manager to release file locks (especially on macOS/Windows)
        # This stops proxy servers and ensures clean deletion
        logger.info("[DEBUG] Calling SandboxManager.reset() to release resources")
        await SandboxManager.reset()
        
        # Delete the sandbox directory
        success = sandbox_service.delete_sandbox(vmcp_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete sandbox directory. Check logs for details."
            )
        
        # Set sandbox_enabled and progressive_discovery_enabled to False in metadata
        try:
            if vmcp_config:
                metadata = getattr(vmcp_config, 'metadata', {}) or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata['sandbox_enabled'] = False
                metadata['progressive_discovery_enabled'] = False
                
                # Update the config with new metadata
                vmcp_config_manager.update_vmcp_config(
                    vmcp_id=vmcp_id,
                    metadata=metadata
                )
                logger.info(f"Disabled sandbox and progressive discovery for vMCP {vmcp_id}")
        except Exception as e:
            logger.warning(f"Failed to update metadata after deleting sandbox for {vmcp_id}: {e}")
            # Don't fail the request if metadata update fails
        
        return {
            "success": True,
            "message": "Sandbox deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting sandbox for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting sandbox: {str(e)}"
        )


@router.get("/status", response_model=SandboxStatusResponse)
async def get_sandbox_status(
    vmcp_id: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Get sandbox status for a vMCP.
    
    Checks metadata flag for enabled state.
    
    Args:
        vmcp_id: The vMCP ID
        user_context: User context from dependency
        
    Returns:
        Sandbox status information
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager
        
        sandbox_service = get_sandbox_service()
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        
        # Load config to check metadata using cached manager
        vmcp_config = None
        try:
            # Import cache function from router_typesafe
            from vmcp.vmcps.router_typesafe import get_cached_vmcp_config_manager
            vmcp_config_manager = get_cached_vmcp_config_manager(user_context.user_id, vmcp_id)
            vmcp_config = vmcp_config_manager.load_vmcp_config()
        except Exception as e:
            logger.debug(f"Could not load vMCP config for status check: {e}")
        
        return SandboxStatusResponse(
            enabled=sandbox_service.is_enabled(vmcp_id, vmcp_config),
            path=str(sandbox_path),
            venv_exists=sandbox_service.venv_exists(vmcp_id),
            folder_exists=sandbox_service.sandbox_exists(vmcp_id)
        )
    except Exception as e:
        logger.error(f"Error getting sandbox status for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting sandbox status: {str(e)}"
        )


@router.get("/files", response_model=List[FileNode])
async def list_sandbox_files(
    vmcp_id: str,
    path: str = "",
    user_context: UserContext = Depends(get_user_context)
):
    """
    List files in the sandbox directory.
    
    Args:
        vmcp_id: The vMCP ID
        path: Optional subdirectory path
        user_context: User context from dependency
        
    Returns:
        List of file nodes
    """
    try:
        sandbox_service = get_sandbox_service()
        
        if not sandbox_service.sandbox_exists(vmcp_id):
            raise HTTPException(
                status_code=404,
                detail="Sandbox not found. Enable sandbox first."
            )
        
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        
        # Resolve the target path
        if path:
            target_path = sandbox_path / path
            # Security: ensure path is within sandbox
            try:
                target_path.resolve().relative_to(sandbox_path.resolve())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid path: path must be within sandbox directory"
                )
        else:
            target_path = sandbox_path
        
        if not target_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Path not found: {path}"
            )
        
        if target_path.is_file():
            # Return single file node
            return [FileNode(
                name=target_path.name,
                path=str(target_path.relative_to(sandbox_path)).replace('\\', '/'),
                type='file',
                size=target_path.stat().st_size,
                modified=str(target_path.stat().st_mtime)
            )]
        
        # Build file tree
        file_tree = _build_file_tree(target_path, sandbox_path)
        return file_tree
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listing files: {str(e)}"
        )


@router.get("/files/{file_path:path}", response_model=FileContentResponse)
async def get_sandbox_file(
    vmcp_id: str,
    file_path: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Read file content from sandbox.
    
    Args:
        vmcp_id: The vMCP ID
        file_path: Path to file relative to sandbox root
        user_context: User context from dependency
        
    Returns:
        File content
    """
    try:
        sandbox_service = get_sandbox_service()
        
        if not sandbox_service.sandbox_exists(vmcp_id):
            raise HTTPException(
                status_code=404,
                detail="Sandbox not found. Enable sandbox first."
            )
        
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        target_file = sandbox_path / file_path
        
        # Security: ensure file is within sandbox
        try:
            target_file.resolve().relative_to(sandbox_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid path: file must be within sandbox directory"
            )
        
        if not target_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )
        
        if not target_file.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a file: {file_path}"
            )
        
        # Check file size (limit to 10MB for safety)
        file_size = target_file.stat().st_size
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="File too large (max 10MB)"
            )
        
        # Read file content
        try:
            content = target_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Binary file - return error
            raise HTTPException(
                status_code=400,
                detail="File appears to be binary. Only text files can be read."
            )
        
        return FileContentResponse(
            content=content,
            path=file_path,
            size=file_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading file {file_path} for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error reading file: {str(e)}"
        )


@router.put("/files/{file_path:path}", response_model=dict)
async def save_sandbox_file(
    vmcp_id: str,
    file_path: str,
    content: str = Form(...),
    user_context: UserContext = Depends(get_user_context)
):
    """
    Save file content to sandbox (create or update).
    
    Args:
        vmcp_id: The vMCP ID
        file_path: Path to file relative to sandbox root
        content: File content
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        sandbox_service = get_sandbox_service()
        
        if not sandbox_service.sandbox_exists(vmcp_id):
            raise HTTPException(
                status_code=404,
                detail="Sandbox not found. Enable sandbox first."
            )
        
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        target_file = sandbox_path / file_path
        
        # Security: ensure file is within sandbox
        try:
            target_file.resolve().relative_to(sandbox_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid path: file must be within sandbox directory"
            )
        
        # Create parent directories if needed
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        target_file.write_text(content, encoding='utf-8')
        
        logger.info(f"Saved file {file_path} for vMCP {vmcp_id}")
        
        return {
            "success": True,
            "message": "File saved successfully",
            "path": file_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving file {file_path} for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error saving file: {str(e)}"
        )


@router.post("/files/upload", response_model=dict)
async def upload_sandbox_file(
    vmcp_id: str,
    file: UploadFile = File(...),
    target_path: Optional[str] = Form(None),
    user_context: UserContext = Depends(get_user_context)
):
    """
    Upload file to sandbox.
    
    Args:
        vmcp_id: The vMCP ID
        file: Uploaded file
        target_path: Optional target path (defaults to filename in root)
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        sandbox_service = get_sandbox_service()
        
        if not sandbox_service.sandbox_exists(vmcp_id):
            raise HTTPException(
                status_code=404,
                detail="Sandbox not found. Enable sandbox first."
            )
        
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        
        # Determine target path
        if target_path:
            target_file = sandbox_path / target_path
        else:
            target_file = sandbox_path / file.filename
        
        # Security: ensure file is within sandbox
        try:
            target_file.resolve().relative_to(sandbox_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid path: file must be within sandbox directory"
            )
        
        # Create parent directories if needed
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Read and write file
        content = await file.read()
        
        # Check file size (limit to 50MB for uploads)
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="File too large (max 50MB)"
            )
        
        # Try to write as text first, fallback to binary
        try:
            text_content = content.decode('utf-8')
            target_file.write_text(text_content, encoding='utf-8')
        except UnicodeDecodeError:
            # Binary file
            target_file.write_bytes(content)
        
        logger.info(f"Uploaded file {target_file.name} to {target_path or 'root'} for vMCP {vmcp_id}")
        
        return {
            "success": True,
            "message": "File uploaded successfully",
            "path": str(target_file.relative_to(sandbox_path)).replace('\\', '/')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )


@router.post("/files/folder", response_model=dict)
async def create_sandbox_folder(
    vmcp_id: str,
    folder_path: str = Form(...),
    user_context: UserContext = Depends(get_user_context)
):
    """
    Create a folder in sandbox.
    
    Args:
        vmcp_id: The vMCP ID
        folder_path: Path to folder relative to sandbox root
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        sandbox_service = get_sandbox_service()
        
        if not sandbox_service.sandbox_exists(vmcp_id):
            raise HTTPException(
                status_code=404,
                detail="Sandbox not found. Enable sandbox first."
            )
        
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        target_folder = sandbox_path / folder_path
        
        # Security: ensure folder is within sandbox
        try:
            target_folder.resolve().relative_to(sandbox_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid path: folder must be within sandbox directory"
            )
        
        if target_folder.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Folder already exists: {folder_path}"
            )
        
        # Create folder
        target_folder.mkdir(parents=True, exist_ok=False)
        
        logger.info(f"Created folder {folder_path} for vMCP {vmcp_id}")
        
        return {
            "success": True,
            "message": "Folder created successfully",
            "path": folder_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating folder {folder_path} for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error creating folder: {str(e)}"
        )


@router.delete("/files/{file_path:path}", response_model=dict)
async def delete_sandbox_file(
    vmcp_id: str,
    file_path: str,
    user_context: UserContext = Depends(get_user_context)
):
    """
    Delete file from sandbox.
    
    Args:
        vmcp_id: The vMCP ID
        file_path: Path to file relative to sandbox root
        user_context: User context from dependency
        
    Returns:
        Success message
    """
    try:
        sandbox_service = get_sandbox_service()
        
        if not sandbox_service.sandbox_exists(vmcp_id):
            raise HTTPException(
                status_code=404,
                detail="Sandbox not found. Enable sandbox first."
            )
        
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        target_file = sandbox_path / file_path
        
        # Security: ensure file is within sandbox
        try:
            target_file.resolve().relative_to(sandbox_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid path: file must be within sandbox directory"
            )
        
        if not target_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )
        
        # Don't allow deleting .venv
        if '.venv' in target_file.parts:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete .venv directory"
            )
        
        # Delete file or directory
        if target_file.is_file():
            target_file.unlink()
        else:
            import shutil
            shutil.rmtree(target_file)
        
        logger.info(f"Deleted {file_path} for vMCP {vmcp_id}")
        
        return {
            "success": True,
            "message": "File deleted successfully",
            "path": file_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {file_path} for {vmcp_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting file: {str(e)}"
        )


# TERMINAL FEATURE DISABLED
# @router.websocket("/terminal")
# async def terminal_websocket(
#     websocket: WebSocket,
#     vmcp_id: str,
#     token: Optional[str] = Query(None),
# ):
#     """
#     WebSocket endpoint for terminal sessions.
#     Creates or reconnects to a persistent PTY session in the sandbox environment.
#     
#     Args:
#         websocket: WebSocket connection
#         vmcp_id: The vMCP ID
#         token: Authentication token from query parameter
#     """
#     await websocket.accept()
#     
#     session_manager = get_terminal_session_manager()
#     session = None
#     
#     try:
#         # Get user context from token
#         # For OSS mode, use dummy user if token is 'local-token' or None
#         if token == 'local-token' or token is None:
#             user_context = UserContext()
#         else:
#             # In production, validate token and create user context
#             # For now, use dummy user
#             user_context = UserContext(token=token)
#         
#         sandbox_service = get_sandbox_service()
#         if not sandbox_service.sandbox_exists(vmcp_id):
#             await websocket.close(code=1008, reason="Sandbox not found")
#             return
#         
#         sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
#         
#         # Get or create persistent terminal session
#         session = await session_manager.get_or_create_session(
#             vmcp_id=vmcp_id,
#             user_id=user_context.user_id,
#             sandbox_path=str(sandbox_path)
#         )
#         
#         # Check if this is a reconnection before registering
#         was_reconnecting = session.active_connections > 0
#         
#         # Register this connection
#         session_manager.register_connection(session.session_id)
#         
#         master_fd = session.master_fd
#         
#         # On reconnection, quickly drain buffered data to restore terminal state
#         # Read synchronously before starting async loop for instant restoration
#         if was_reconnecting:
#             try:
#                 # Read buffered data in tight loop for fast restoration
#                 buffered_data = []
#                 for _ in range(100):  # Read many times to drain buffer
#                     ready, _, _ = select.select([master_fd], [], [], 0)
#                     if not ready:
#                         break
#                     try:
#                         data = os.read(master_fd, 131072)  # Large chunks
#                         if data:
#                             buffered_data.append(data)
#                         else:
#                             break
#                     except OSError:
#                         break
#                 
#                 # Send all buffered data at once for speed
#                 if buffered_data:
#                     await websocket.send_bytes(b''.join(buffered_data))
#                 
#                 # Trigger a refresh for programs like vi (Ctrl+L equivalent)
#                 # This helps restore display without corrupting it
#                 os.write(master_fd, b'\x0c')  # Form feed (Ctrl+L) - standard terminal refresh
#                 
#             except Exception as e:
#                 logger.debug(f"Error restoring terminal state on reconnection: {e}")
#         
#         # Flag to track if we should continue
#         should_continue = True
#         
#         # Start tasks for reading from PTY and writing to WebSocket
#         async def read_from_pty():
#             nonlocal should_continue
#             
#             # Main read loop - optimized for maximum responsiveness
#             consecutive_empty_reads = 0
#             while should_continue:
#                 try:
#                     # Check if websocket is still connected
#                     if websocket.client_state.name != 'CONNECTED':
#                         should_continue = False
#                         break
#                     
#                     # Use select with minimal timeout for responsiveness
#                     ready, _, _ = select.select([master_fd], [], [], 0.001)  # 1ms timeout
#                     if ready:
#                         try:
#                             data = os.read(master_fd, 131072)  # Large buffer for throughput
#                             if data:
#                                 consecutive_empty_reads = 0
#                                 try:
#                                     await websocket.send_bytes(data)
#                                     # Continue immediately if there might be more data
#                                     continue
#                                 except (WebSocketDisconnect, RuntimeError):
#                                     should_continue = False
#                                     break
#                         except OSError:
#                             pass
#                     
#                     # Very short sleep when idle to avoid busy-waiting
#                     consecutive_empty_reads += 1
#                     if consecutive_empty_reads > 10:
#                         await asyncio.sleep(0.0005)  # 0.5ms sleep when truly idle
#                         consecutive_empty_reads = 0
#                         
#                 except (WebSocketDisconnect, RuntimeError):
#                     # WebSocket disconnected
#                     should_continue = False
#                     break
#                 except Exception as e:
#                     logger.error(f"Error reading from PTY: {e}")
#                     should_continue = False
#                     break
#         
#         async def write_to_pty():
#             nonlocal should_continue
#             while should_continue:
#                 try:
#                     # Check if websocket is still connected before trying to receive
#                     if websocket.client_state.name != 'CONNECTED':
#                         should_continue = False
#                         break
#                     
#                     message = await websocket.receive()
#                     
#                     # Handle binary data (raw terminal input)
#                     if 'bytes' in message:
#                         bytes_data = message['bytes']
#                         # Ensure bytes_data is actually bytes
#                         if isinstance(bytes_data, bytes):
#                             os.write(master_fd, bytes_data)
#                         elif isinstance(bytes_data, (str, int)):
#                             # Convert to bytes if needed
#                             if isinstance(bytes_data, str):
#                                 os.write(master_fd, bytes_data.encode())
#                             else:
#                                 # Shouldn't happen, but handle gracefully
#                                 logger.warning(f"Unexpected bytes type: {type(bytes_data)}")
#                                 continue
#                         else:
#                             logger.warning(f"Unexpected bytes data type: {type(bytes_data)}")
#                             continue
#                     
#                     # Handle text data (JSON messages or raw text)
#                     elif 'text' in message:
#                         text_data = message['text']
#                         if not isinstance(text_data, str):
#                             logger.warning(f"Unexpected text type: {type(text_data)}")
#                             continue
#                         
#                         try:
#                             data = json.loads(text_data)
#                             # Ensure data is a dict before calling .get()
#                             if isinstance(data, dict):
#                                 if data.get('type') == 'resize':
#                                     # Handle terminal resize
#                                     rows = data.get('rows', 24)
#                                     cols = data.get('cols', 80)
#                                     winsize = struct.pack('HHHH', rows, cols, 0, 0)
#                                     fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
#                                 elif 'input' in data:
#                                     input_str = data.get('input', '')
#                                     if isinstance(input_str, str):
#                                         os.write(master_fd, input_str.encode())
#                             else:
#                                 # Not a dict, treat as raw input
#                                 os.write(master_fd, text_data.encode())
#                         except json.JSONDecodeError:
#                             # Not JSON, treat as raw input
#                             os.write(master_fd, text_data.encode())
#                 except WebSocketDisconnect:
#                     should_continue = False
#                     break
#                 except RuntimeError as e:
#                     # RuntimeError can occur when trying to receive after disconnect
#                     if "disconnect" in str(e).lower() or "receive" in str(e).lower():
#                         should_continue = False
#                         break
#                     logger.error(f"Error writing to PTY: {e}")
#                     should_continue = False
#                     break
#                 except Exception as e:
#                     logger.error(f"Error writing to PTY: {e}")
#                     should_continue = False
#                     break
#         
#         # On reconnection, create a task to flush and trigger prompt refresh
#         # This runs concurrently with read/write loops, matching first-connection flow
#         async def reconnect_flush_and_prompt():
#             if was_reconnecting:
#                 # Small delay to let read loop start first
#                 await asyncio.sleep(0.01)
#                 try:
#                     # Quick flush of any buffered data
#                     flushed_chunks = []
#                     for _ in range(50):  # Quick drain
#                         ready, _, _ = select.select([master_fd], [], [], 0)
#                         if not ready:
#                             break
#                         try:
#                             data = os.read(master_fd, 131072)
#                             if data:
#                                 flushed_chunks.append(data)
#                             else:
#                                 break
#                         except OSError:
#                             break
#                     
#                     # Send flushed data if any
#                     if flushed_chunks:
#                         await websocket.send_bytes(b''.join(flushed_chunks))
#                     
#                     # Trigger prompt refresh - read loop will handle reading it naturally
#                     os.write(master_fd, b'\r\n')
#                 except Exception as e:
#                     logger.debug(f"Error triggering prompt refresh: {e}")
#         
#         try:
#             # Run all tasks concurrently
#             # Read loop starts immediately (like first connection), so prompt appears smoothly
#             tasks = [
#                 read_from_pty(),
#                 write_to_pty(),
#             ]
#             if was_reconnecting:
#                 tasks.append(reconnect_flush_and_prompt())
#             
#             await asyncio.gather(*tasks, return_exceptions=True)
#         finally:
#             # Unregister connection (but don't close session - it persists)
#             if session:
#                 session_manager.unregister_connection(session.session_id)
#                     
#     except WebSocketDisconnect:
#         logger.info(f"WebSocket disconnected for vMCP {vmcp_id}")
#         if session:
#             session_manager.unregister_connection(session.session_id)
#     except Exception as e:
#         logger.error(f"Error in terminal WebSocket for vMCP {vmcp_id}: {e}", exc_info=True)
#         if session:
#             session_manager.unregister_connection(session.session_id)
#         try:
#             await websocket.close(code=1011, reason=f"Server error: {str(e)}")
#         except Exception:
#             pass

