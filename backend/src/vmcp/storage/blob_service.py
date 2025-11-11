import uuid
import mimetypes
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
from fastapi import UploadFile, HTTPException
from dataclasses import dataclass
import logging

# OSS-specific imports
from .database import get_db
from .models import Blob

logger = logging.getLogger("BLOB_SERVICE")

@dataclass
class BlobMetadata:
    id: str
    original_filename: str
    filename: str
    resource_name: str
    content_type: str
    size: int
    vmcp_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def dict(self):
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "filename": self.filename,
            "resource_name": self.resource_name,
            "content_type": self.content_type,
            "size": self.size,
            "vmcp_id": self.vmcp_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class BlobStorageManager:
    """Manages blob storage operations using SQLite database"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        
    def store_blob(self, file: UploadFile, vmcp_id: Optional[str] = None) -> BlobMetadata:
        """Store a file as a blob in SQLite database"""
        try:
            # Validate file size (10MB limit)
            if file.size and file.size > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
            
            # Generate unique blob ID
            blob_id = str(uuid.uuid4())
            
            # Normalize the original filename
            original_name = file.filename or "unknown_file"
            normalized_name = "".join(c for c in original_name if c.isalnum() or c in "._-").rstrip()
            
            # Get file extension
            file_ext = Path(original_name).suffix if original_name else ""
            
            # Create stored filename: normalized_name_blob_id.ext
            if normalized_name and normalized_name != "unknown_file":
                stored_filename = f"{normalized_name}_{blob_id}{file_ext}"
            else:
                stored_filename = f"{blob_id}{file_ext}"
            
            # Detect MIME type if not provided
            content_type = file.content_type
            if not content_type:
                content_type, _ = mimetypes.guess_type(file.filename or stored_filename)
                if not content_type:
                    content_type = "application/octet-stream"
            
            # Read file content
            file_content = file.file.read()
            file_size = len(file_content)
            
            # Store in database
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
                    user_id=self.user_id,
                    original_filename=original_name,
                    filename=stored_filename,
                    resource_name=f"file://{normalized_name}",
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
                
                # Create blob metadata
                blob_metadata = BlobMetadata(
                    id=blob_id,
                    original_filename=original_name,
                    filename=stored_filename,
                    resource_name=f"file://{normalized_name}",
                    content_type=content_type,
                    size=file_size,
                    vmcp_id=vmcp_id,
                    user_id=str(self.user_id),
                    created_at=datetime.now()
                )
                
                logger.info(f"Successfully stored blob {blob_id} for user {self.user_id}")
                return blob_metadata
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error storing blob: {e}")
            raise HTTPException(status_code=500, detail="Failed to store blob")
    
    def get_blob_metadata(self, blob_id: str, vmcp_id: Optional[str] = None) -> Optional[BlobMetadata]:
        """Get blob metadata by ID"""
        try:
            db = next(get_db())
            try:
                query = db.query(Blob).filter(Blob.id == blob_id, Blob.user_id == self.user_id)
                if vmcp_id:
                    query = query.filter(Blob.vmcp_id == vmcp_id)
                
                blob = query.first()
                if not blob:
                    return None
                
                return BlobMetadata(
                    id=blob.id,
                    original_filename=blob.original_filename,
                    filename=blob.filename,
                    resource_name=blob.resource_name,
                    content_type=blob.content_type,
                    size=blob.size,
                    vmcp_id=blob.vmcp_id,
                    user_id=str(blob.user_id),
                    created_at=blob.created_at
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting blob metadata {blob_id}: {e}")
            return None
    
    def get_blob_content(self, blob_id: str, vmcp_id: Optional[str] = None) -> Optional[Union[str, bytes]]:
        """Get blob content by ID - returns text for text files, bytes for binary files"""
        try:
            db = next(get_db())
            try:
                query = db.query(Blob).filter(Blob.id == blob_id, Blob.user_id == self.user_id)
                if vmcp_id:
                    query = query.filter(Blob.vmcp_id == vmcp_id)
                
                blob = query.first()
                if not blob:
                    logger.error(f"Blob not found for {blob_id}")
                    return None
                
                if blob.content_type and "text" in blob.content_type:
                    # Text files are stored as-is
                    return blob.content
                else:
                    # Binary files are stored as base64
                    return base64.b64decode(blob.content)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting blob content {blob_id}: {e}")
            return None
    
    def list_blobs(self, vmcp_id: Optional[str] = None) -> List[BlobMetadata]:
        """List all blobs, optionally filtered by vmcp"""
        try:
            db = next(get_db())
            try:
                query = db.query(Blob).filter(Blob.user_id == self.user_id)
                if vmcp_id:
                    query = query.filter(Blob.vmcp_id == vmcp_id)
                
                blobs = query.all()
                return [
                    BlobMetadata(
                        id=blob.id,
                        original_filename=blob.original_filename,
                        filename=blob.filename,
                        resource_name=blob.resource_name,
                        content_type=blob.content_type,
                        size=blob.size,
                        vmcp_id=blob.vmcp_id,
                        user_id=str(blob.user_id),
                        created_at=blob.created_at
                    )
                    for blob in blobs
                ]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error listing blobs: {e}")
            return []
    
    def delete_blob(self, blob_id: str, vmcp_id: Optional[str] = None) -> bool:
        """Delete a blob"""
        try:
            db = next(get_db())
            try:
                query = db.query(Blob).filter(Blob.id == blob_id, Blob.user_id == self.user_id)
                if vmcp_id:
                    query = query.filter(Blob.vmcp_id == vmcp_id)
                
                blob = query.first()
                if not blob:
                    logger.error(f"Blob {blob_id} not found for deletion")
                    return False
                
                db.delete(blob)
                db.commit()
                logger.info(f"Successfully deleted blob {blob_id}")
                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error deleting blob {blob_id}: {e}")
            return False
    
    def rename_blob(self, blob_id: str, new_original_filename: str, vmcp_id: Optional[str] = None) -> Optional[BlobMetadata]:
        """Rename a blob's original filename"""
        try:
            db = next(get_db())
            try:
                query = db.query(Blob).filter(Blob.id == blob_id, Blob.user_id == self.user_id)
                if vmcp_id:
                    query = query.filter(Blob.vmcp_id == vmcp_id)
                
                blob = query.first()
                if not blob:
                    logger.error(f"Blob {blob_id} not found for renaming")
                    return None
                
                # Update the original filename and resource name
                blob.original_filename = new_original_filename
                
                # Update resource_name (normalized version)
                resource_name = "".join(c for c in new_original_filename if c.isalnum() or c in "._-").rstrip()
                if not resource_name:
                    resource_name = "unknown_file"
                blob.resource_name = f"file://{resource_name}"
                
                # Update stored filename
                file_ext = Path(new_original_filename).suffix if new_original_filename else ""
                if resource_name and resource_name != "unknown_file":
                    blob.filename = f"{resource_name}_{blob_id}{file_ext}"
                else:
                    blob.filename = f"{blob_id}{file_ext}"
                
                db.commit()
                db.refresh(blob)
                
                logger.info(f"Successfully renamed blob {blob_id} to '{new_original_filename}'")
                
                return BlobMetadata(
                    id=blob.id,
                    original_filename=blob.original_filename,
                    filename=blob.filename,
                    resource_name=blob.resource_name,
                    content_type=blob.content_type,
                    size=blob.size,
                    vmcp_id=blob.vmcp_id,
                    user_id=str(blob.user_id),
                    created_at=blob.created_at
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error renaming blob {blob_id}: {e}")
            return None 