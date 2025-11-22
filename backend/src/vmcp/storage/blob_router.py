from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import FileResponse, Response
from typing import List, Optional, Union, Any
from pydantic import BaseModel
import uuid
import base64
from datetime import datetime
from pathlib import Path

# OSS-specific imports
from .blob_service import BlobMetadata
from .dummy_user import get_user_context, UserContext
from .database import get_db
from .models import Blob
from ..vmcps.vmcp_config_manager.config_core import VMCPConfigManager

import logging
from vmcp.utilities.logging import setup_logging

logger = setup_logging("BLOB_ROUTER")

# Try to import GlobalBlob for Enterprise (public vMCPs)
GlobalBlob = None
try:
    import importlib.util
    from pathlib import Path as PathLib
    # Try to find Enterprise models
    current_file = PathLib(__file__)
    # Go up to project root: oss/backend/src/vmcp/storage/blob_router.py -> enterprise/backend/src/vmcp/storage/models.py
    enterprise_models_path = current_file.parent.parent.parent.parent.parent.parent / "enterprise" / "backend" / "src" / "vmcp" / "storage" / "models.py"
    if enterprise_models_path.exists():
        spec = importlib.util.spec_from_file_location("enterprise_vmcp_storage_models", enterprise_models_path)
        if spec is not None and spec.loader is not None:
            enterprise_models = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(enterprise_models)
            if hasattr(enterprise_models, 'GlobalBlob'):
                GlobalBlob = enterprise_models.GlobalBlob
                logger.debug("Successfully imported GlobalBlob for public vMCP blob access")
except Exception as e:
    logger.debug(f"GlobalBlob not available (OSS mode or Enterprise not found): {e}")

router = APIRouter(prefix="/blob", tags=["blob"])

class DeleteBlobRequest(BaseModel):
    vmcp_id: Optional[str] = None

class RenameBlobRequest(BaseModel):
    new_filename: str
    vmcp_id: Optional[str] = None

def get_blob_from_db(db, blob_id: str, vmcp_id: Optional[str], user_id: str) -> Optional[Union[Blob, Any]]:
    """
    Get blob from database, checking GlobalBlob for public vMCPs first, then user's Blob table.
    Returns a blob-like object (either Blob or GlobalBlob).
    """
    # Check if this is a public vMCP (Enterprise only - public vMCPs have "@" in ID)
    is_public_vmcp = vmcp_id and vmcp_id.startswith("@")
    
    if is_public_vmcp and GlobalBlob:
        # Try GlobalBlob first for public vMCPs
        try:
            query = db.query(GlobalBlob).filter(GlobalBlob.id == blob_id)
            if vmcp_id:
                query = query.filter(GlobalBlob.public_vmcp_id == vmcp_id)
            
            global_blob = query.first()
            if global_blob:
                # Create a wrapper to make GlobalBlob compatible with Blob interface
                class BlobWrapper:
                    def __init__(self, global_blob):
                        self.id = global_blob.id
                        self.content = global_blob.content
                        self.content_type = global_blob.content_type
                        self.original_filename = global_blob.original_filename
                        self.filename = global_blob.filename
                        self.resource_name = global_blob.resource_name
                        self.size = global_blob.size
                
                logger.debug(f"Found global blob {blob_id} for public vMCP {vmcp_id}")
                return BlobWrapper(global_blob)
        except Exception as e:
            logger.debug(f"Error querying GlobalBlob: {e}")
    
    # Fall back to user's Blob table
    query = db.query(Blob).filter(Blob.id == blob_id, Blob.user_id == user_id)
    if vmcp_id:
        query = query.filter(Blob.vmcp_id == vmcp_id)
    
    blob = query.first()
    if blob:
        logger.debug(f"Found user blob {blob_id} for vMCP {vmcp_id}")
    
    return blob

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    vmcp_id: Optional[str] = Form(None),
    user_context = Depends(get_user_context)
):
    """Upload a file and return its URL (frontend compatibility)"""
    try:
        # Validate file size (10MB limit)
        if file.size and file.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Validate vmcp_id if provided
        if vmcp_id:
            vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
            vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
            if not vmcp:
                raise HTTPException(status_code=404, detail="vMCP not found")
        
        # Generate unique blob ID
        blob_id = str(uuid.uuid4())
        
        # Get file metadata
        original_filename = file.filename or "unknown_file"
        content_type = file.content_type or "application/octet-stream"
        
        # Normalize the original filename for resource_name
        resource_name = "".join(c for c in original_filename if c.isalnum() or c in "._-").rstrip()
        if not resource_name:
            resource_name = "unknown_file"
        
        # Create stored filename
        file_ext = Path(original_filename).suffix if original_filename else ""
        if resource_name and resource_name != "unknown_file":
            stored_filename = f"{resource_name}_{blob_id}{file_ext}"
        else:
            stored_filename = f"{blob_id}{file_ext}"
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Store directly in database using OSS database session
        db = next(get_db())
        try:
            # Encode binary content as base64 for SQLite Text storage
            if content_type.startswith('text/'):
                # For text files, store as-is
                content_str = file_content.decode('utf-8')
            else:
                # For binary files, encode as base64
                content_str = base64.b64encode(file_content).decode('utf-8')
            
            # Create blob record
            new_blob = Blob(
                id=blob_id,
                user_id=user_context.user_id,
                original_filename=original_filename,
                filename=stored_filename,
                resource_name=f"file://{resource_name}",
                content=content_str,
                content_type=content_type,
                size=file_size,
                vmcp_id=vmcp_id,
                widget_id=None,  # Not a widget file
                is_public=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            db.add(new_blob)
            db.commit()
            db.refresh(new_blob)
            
            logger.info(f"Successfully stored blob {blob_id} for user {user_context.user_id}")
            
            # Add to vMCP resources if vmcp_id provided
            if vmcp_id:
                vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
                blob_dict = {
                    "id": blob_id,
                    "original_filename": original_filename,
                    "filename": stored_filename,
                    "resource_name": f"file://{resource_name}",
                    "content_type": content_type,
                    "size": file_size,
                    "vmcp_id": vmcp_id,
                    "user_id": str(user_context.user_id),
                    "created_at": new_blob.created_at.isoformat() if new_blob.created_at else None
                }
                result = vmcp_manager.add_resource(vmcp_id, blob_dict)
                if not result:
                    logger.warning(f"Failed to add resource {blob_id} to vMCP {vmcp_id}")
                else:
                    logger.info(f"Successfully added resource {blob_id} to vMCP {vmcp_id}")
            
            return {
                "blob_id": blob_id,
                "url": f"/api/blob/{blob_id}",
                "original_name": original_filename,
                "normalized_name": stored_filename,
                "stored_filename": stored_filename,
                "resource_name": resource_name,
                "size": file_size,
                "vmcp_id": vmcp_id,
                "user_id": user_context.user_id
            }
        finally:
            db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")

@router.get("/content/{blob_id}")
async def get_blob_content(
    blob_id: str,
    user_context = Depends(get_user_context),
    vmcp_id: Optional[str] = Query(None)
):
    """Get blob content as JSON data for frontend viewing"""
    if vmcp_id:
        # Validate vmcp_id if provided
        vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
        vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
        if not vmcp:
            raise HTTPException(status_code=404, detail="vMCP not found")
    
    # Get blob from database (checks GlobalBlob for public vMCPs, then user's Blob table)
    db = next(get_db())
    try:
        blob = get_blob_from_db(db, blob_id, vmcp_id, user_context.user_id)
        if not blob:
            raise HTTPException(status_code=404, detail="Blob not found")
        
        # For text files, return the content as text
        if blob.content_type and blob.content_type.startswith('text/'):
            return {
                "content": blob.content,
                "content_type": blob.content_type,
                "size": blob.size,
                "filename": blob.original_filename
            }
        
        # For binary files, return the content as base64 encoded string
        return {
            "content": blob.content,  # Already base64 encoded
            "content_type": blob.content_type,
            "size": blob.size,
            "filename": blob.original_filename,
            "binary": True
        }
    finally:
        db.close()

@router.get("/{blob_id}")
async def get_file(
    blob_id: str,
    user_context = Depends(get_user_context),
    vmcp_id: Optional[str] = Query(None)
):
    """Serve a file by its blob ID (frontend compatibility)"""
    if vmcp_id:
        # Validate vmcp_id if provided
        vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
        vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
        if not vmcp:
            raise HTTPException(status_code=404, detail="vMCP not found")
    
    # Get blob from database (checks GlobalBlob for public vMCPs, then user's Blob table)
    db = next(get_db())
    try:
        blob = get_blob_from_db(db, blob_id, vmcp_id, user_context.user_id)
        if not blob:
            raise HTTPException(status_code=404, detail="Blob not found")
        
        # Decode content based on type
        if blob.content_type.startswith('text/'):
            # Text files are stored as-is
            content = blob.content.encode('utf-8')
        else:
            # Binary files are stored as base64
            content = base64.b64decode(blob.content)
        
        # Return the file content directly
        return Response(
            content=content,
            media_type=blob.content_type,
            headers={
                "Content-Disposition": f"attachment; filename={blob.original_filename}",
                "Content-Length": str(blob.size)
            }
        )
    finally:
        db.close()

@router.get("/resource/{resource_id}")
async def get_resource(
    resource_id: str,
    user_context = Depends(get_user_context),
    vmcp_id: Optional[str] = Query(None)
):
    """Serve a resource by its resource ID directly from database"""
    if vmcp_id:
        # Validate vmcp_id if provided
        vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
        vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
        if not vmcp:
            raise HTTPException(status_code=404, detail="vMCP not found")
    
    # Get resource from database (checks GlobalBlob for public vMCPs, then user's Blob table)
    db = next(get_db())
    try:
        blob = get_blob_from_db(db, resource_id, vmcp_id, user_context.user_id)
        if not blob:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Decode content based on type
        if blob.content_type.startswith('text/'):
            # Text files are stored as-is
            content = blob.content.encode('utf-8')
        else:
            # Binary files are stored as base64
            content = base64.b64decode(blob.content)
        
        # Return the resource content directly
        return Response(
            content=content,
            media_type=blob.content_type,
            headers={
                "Content-Disposition": f"attachment; filename={blob.original_filename}",
                "Content-Length": str(blob.size)
            }
        )
        
    finally:
        db.close()

@router.delete("/{blob_id}")
async def delete_file(
    blob_id: str,
    user_context = Depends(get_user_context),
    vmcp_id: Optional[str] = Query(None)
):
    """Delete a blob (frontend compatibility)"""
    if vmcp_id:
        # Validate vmcp_id if provided
        vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
        vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
        if not vmcp:
            raise HTTPException(status_code=404, detail="vMCP not found")
    
    # Delete blob from database
    db = next(get_db())
    try:
        query = db.query(Blob).filter(Blob.id == blob_id, Blob.user_id == user_context.user_id)
        if vmcp_id:
            query = query.filter(Blob.vmcp_id == vmcp_id)
        
        blob = query.first()
        if not blob:
            raise HTTPException(status_code=404, detail="Blob not found")
        
        # Delete the blob
        db.delete(blob)
        db.commit()

        # delete vMCP resources if vmcp_id provided
        if vmcp_id:
            vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
            blob_dict = {
                "id": blob.id,
                "original_filename": blob.original_filename,
                "filename": blob.filename,
                "resource_name": blob.resource_name,
                "content_type": blob.content_type,
                "size": blob.size,
                "vmcp_id": vmcp_id,
                "user_id": str(user_context.user_id),
                "created_at": blob.created_at.isoformat() if blob.created_at else None
            }
            result = vmcp_manager.delete_resource(vmcp_id, blob_dict)
            if not result:
                logger.warning(f"Failed to delete resource {blob_id} from vMCP {vmcp_id}")
            else:
                logger.info(f"Successfully deleted resource {blob_id} from vMCP {vmcp_id}")
        
        logger.info(f"Successfully deleted blob {blob_id} for user {user_context.user_id}")
        return {"message": f"Blob {blob_id} deleted successfully"}
    finally:
        db.close()

@router.patch("/{blob_id}/rename")
async def rename_file(
    blob_id: str,
    request: RenameBlobRequest,
    user_context = Depends(get_user_context),
):
    """Rename a blob's original filename (frontend compatibility)"""
    vmcp_id = request.vmcp_id
    logger.info(f"vmcp_id: {vmcp_id}")
    
    new_filename = request.new_filename
    logger.info(f"new_filename: {new_filename}")
    # Update blob in database
    from auth_service.models import Blob
    from auth_service.database import SessionLocal
    from pathlib import Path
    
    db = SessionLocal()
    try:
        query = db.query(Blob).filter(Blob.blob_id == blob_id, Blob.user_id == user_context.user_id)
        if vmcp_id:
            query = query.filter(Blob.vmcp_id == vmcp_id)
        
        blob = query.first()
        if not blob:
            raise HTTPException(status_code=404, detail="Blob not found")
        logger.info(f"blob: {blob}")
        # Update the original filename and resource name
        blob.original_filename = new_filename
        
        # Update resource_name (normalized version)
        resource_name = "".join(c for c in new_filename if c.isalnum() or c in "._-").rstrip()
        if not resource_name:
            resource_name = "unknown_file"
        blob.resource_name = f"file://{resource_name}"
        
        # Update stored filename
        file_ext = Path(new_filename).suffix if new_filename else ""
        if resource_name and resource_name != "unknown_file":
            blob.filename = f"{resource_name}_{blob_id}{file_ext}"
        else:
            blob.filename = f"{blob_id}{file_ext}"
        
        db.commit()
        db.refresh(blob)

        # update vMCP resources if vmcp_id provided
        if vmcp_id:
            vmcp_manager = VMCPConfigManager(user_context.user_id)
            blob_dict = {
                "id": blob.blob_id,
                "original_filename": blob.original_filename,
                "filename": blob.filename,
                "resource_name": blob.resource_name,
                "content_type": blob.content_type,
                "size": blob.size,
                "vmcp_id": vmcp_id,
                "user_id": str(user_context.user_id),
                "created_at": blob.created_at.isoformat() if blob.created_at else None
            }
            result = vmcp_manager.update_resource(vmcp_id, blob_dict)
            if not result:
                logger.warning(f"Failed to update resource {blob_id} to vMCP {vmcp_id}")
            else:
                logger.info(f"Successfully updated resource {blob_id} to vMCP {vmcp_id}")
        
        logger.info(f"Successfully renamed blob {blob_id} to {new_filename}")


        
        return {
            "message": f"Blob {blob_id} renamed successfully",
            "blob_id": blob.blob_id,
            "original_name": blob.original_filename,
            "resource_name": blob.resource_name,
            "original_filename": blob.original_filename,
            "filename": blob.filename,
            "url": f"/api/blob/{blob.blob_id}",
            "size": blob.size
        }
        
    finally:
        db.close()

@router.get("/")
async def list_blobs_general(
    vmcp_id: Optional[str] = Query(None),
    user_context = Depends(get_user_context),
):
    """List all blobs for the authenticated user (frontend compatibility)"""
    try:
        if vmcp_id:
            # Validate vmcp_id if provided
            vmcp_manager = VMCPConfigManager(user_id=user_context.user_id, vmcp_id=vmcp_id)
            vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
            if not vmcp:
                raise HTTPException(status_code=404, detail="vMCP not found")
        
        # Get blobs from database
        db = next(get_db())
        try:
            query = db.query(Blob).filter(Blob.user_id == user_context.user_id)
            if vmcp_id:
                query = query.filter(Blob.vmcp_id == vmcp_id)
            
            blobs = query.order_by(Blob.created_at.desc()).all()
            
            # Convert to frontend-compatible format
            blob_list = []
            for blob in blobs:
                blob_list.append({
                    "blob_id": blob.id,
                    "url": f"/api/blob/{blob.id}",
                    "original_name": blob.original_filename,
                    "normalized_name": blob.filename,
                    "stored_filename": blob.filename,
                    "content_type": blob.content_type,
                    "mime_type": blob.content_type,
                    "resource_name": blob.resource_name,
                    "size": blob.size,
                    "vmcp_id": blob.vmcp_id,
                    "user_id": user_context.user_id,
                    "uploaded_at": blob.created_at.isoformat() if blob.created_at else None
                })
            
            return {
                "blobs": blob_list,
                "total": len(blob_list),
                "user_id": user_context.user_id
            }
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error listing blobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list blobs")

@router.get("/blobs/{blob_id}")
async def download_blob(
    blob_id: str,
    user_context: UserContext = Depends(get_user_context),
    vmcp_id: Optional[str] = Query(None)
):
    """Download a blob file"""
    if vmcp_id:
        # Validate vmcp_id if provided
        from vmcps.vmcp_config_manager import VMCPConfigManager
        vmcp_manager = VMCPConfigManager(user_context.user_id)
        vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
        if not vmcp:
            raise HTTPException(status_code=404, detail="vMCP not found")
    
    # Get blob from database
    from auth_service.models import Blob
    from auth_service.database import SessionLocal
    from fastapi.responses import Response
    
    db = SessionLocal()
    try:
        query = db.query(Blob).filter(Blob.blob_id == blob_id, Blob.user_id == user_context.user_id)
        if vmcp_id:
            query = query.filter(Blob.vmcp_id == vmcp_id)
        
        blob = query.first()
        if not blob:
            raise HTTPException(status_code=404, detail="Blob not found")
        
        # Create a response with the content
        headers = {
            "Content-Disposition": f"attachment; filename={blob.original_filename}",
            "Content-Length": str(blob.size)
        }
        
        return Response(
            content=blob.file_data,
            media_type=blob.content_type,
            headers=headers
        )
        
    finally:
        db.close()

@router.get("/blobs/{blob_id}/metadata", response_model=BlobMetadata)
async def get_blob_metadata(
    blob_id: str,
    user_context: UserContext = Depends(get_user_context),
    vmcp_id: Optional[str] = Query(None)
):
    """Get metadata about a blob"""
    if vmcp_id:
        # Validate vmcp_id if provided
        from vmcps.vmcp_config_manager import VMCPConfigManager
        vmcp_manager = VMCPConfigManager(user_context.user_id)
        vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
        if not vmcp:
            raise HTTPException(status_code=404, detail="vMCP not found")
    
    # Get blob from database
    from auth_service.models import Blob
    from auth_service.database import SessionLocal
    from storage.blob_service import BlobMetadata
    
    db = SessionLocal()
    try:
        query = db.query(Blob).filter(Blob.blob_id == blob_id, Blob.user_id == user_context.user_id)
        if vmcp_id:
            query = query.filter(Blob.vmcp_id == vmcp_id)
        
        blob = query.first()
        if not blob:
            raise HTTPException(status_code=404, detail="Blob not found")
        
        # Convert to BlobMetadata
        blob_metadata = BlobMetadata(
            id=blob.blob_id,
            original_filename=blob.original_filename,
            filename=blob.filename,
            resource_name=blob.resource_name,
            content_type=blob.content_type,
            size=blob.size,
            vmcp_id=blob.vmcp_id,
            agent_id=blob.agent_id,
            user_id=str(blob.user_id),
            created_at=blob.created_at.isoformat() if blob.created_at else None
        )
        
        return blob_metadata
        
    finally:
        db.close()

@router.delete("/blobs/{blob_id}")
async def delete_blob(
    blob_id: str,
    user_context: UserContext = Depends(get_user_context),
    vmcp_id: Optional[str] = Query(None)
):
    """Delete a blob"""
    if vmcp_id:
        # Validate vmcp_id if provided
        from vmcps.vmcp_config_manager import VMCPConfigManager
        vmcp_manager = VMCPConfigManager(user_context.user_id)
        vmcp = vmcp_manager.load_vmcp_config(specific_vmcp_id=vmcp_id)
        if not vmcp:
            raise HTTPException(status_code=404, detail="vMCP not found")
    
    # Delete blob from database
    from auth_service.models import Blob
    from auth_service.database import SessionLocal
    
    db = SessionLocal()
    try:
        query = db.query(Blob).filter(Blob.blob_id == blob_id, Blob.user_id == user_context.user_id)
        if vmcp_id:
            query = query.filter(Blob.vmcp_id == vmcp_id)
        
        blob = query.first()
        if not blob:
            raise HTTPException(status_code=404, detail="Blob not found")
        
        # Delete the blob
        db.delete(blob)
        db.commit()
        
        logger.info(f"Successfully deleted blob {blob_id} for user {user_context.user_id}")
        return {"message": f"Blob {blob_id} deleted successfully"}
        
    finally:
        db.close() 