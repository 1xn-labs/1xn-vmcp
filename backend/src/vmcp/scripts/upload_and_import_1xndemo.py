#!/usr/bin/env python3
"""
Script to upload 1xndemo to public registry and import it to private VMCP table.
Uses the same import flow as the normal import process.

This script:
1. Uploads 1xndemo_config.json to GlobalPublicVMCPRegistry (like demo vMCPs)
2. Imports it to the private VMCP table using the same import flow
"""

import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from vmcp.vmcps.models import VMCPConfig
from vmcp.storage.database import init_db, SessionLocal
from vmcp.storage.models import GlobalPublicVMCPRegistry, Blob
from vmcp.vmcps.vmcp_config_manager.config_core import VMCPConfigManager
from rich.console import Console
import uuid
import base64
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upload_and_import_1xndemo")

# Get the package root directory
PACKAGE_ROOT = Path(__file__).parent.parent
DATA_DIR = PACKAGE_ROOT / "data"
XNDEMO_FILE = DATA_DIR / "1xndemo_config.json"
PUBLIC_VMCP_ID = "1xndemo"


def load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse a JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return None


def upload_and_update_custom_resources_for_1xndemo(session, json_data: Dict[str, Any]) -> bool:
    """Upload blob files referenced in custom_resources to user's Blob table and update custom_resources (OSS only - no public vMCPs)"""
    try:
        custom_resources = json_data.get("custom_resources", [])
        if not custom_resources:
            logger.info("No custom_resources found in 1xndemo config")
            return True
        
        user_id = int(json_data.get("user_id", "1"))
        updated_resources = []
        
        for resource in custom_resources:
            original_filename = resource.get("original_filename")
            if not original_filename:
                # Keep resources without filenames as-is (e.g., URI-based resources)
                updated_resources.append(resource)
                continue
            
            # Find the actual file in the data directory
            file_path = DATA_DIR / original_filename
            
            if not file_path.exists():
                # Try alternative paths
                import os
                cwd = Path(os.getcwd())
                alt_path = cwd / "oss" / "backend" / "src" / "vmcp" / "data" / original_filename
                if alt_path.exists():
                    file_path = alt_path
                else:
                    logger.warning(f"File {original_filename} not found, skipping custom resource")
                    # Keep original resource entry even if file not found
                    updated_resources.append(resource)
                    continue
            
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            file_size = len(file_content)
            normalized_name = Path(original_filename).stem
            
            # Generate unique blob ID
            blob_id = str(uuid.uuid4())
            
            # Create stored filename
            file_ext = Path(original_filename).suffix
            stored_filename = f"{normalized_name}_{blob_id}{file_ext}"
            
            # Encode binary content as base64
            content_type = resource.get("content_type", "application/octet-stream")
            if content_type.startswith('text/'):
                content_str = file_content.decode('utf-8')
            else:
                content_str = base64.b64encode(file_content).decode('utf-8')
            
            # Create Blob record in user's storage (OSS doesn't have public vMCPs)
            new_blob = Blob(
                id=blob_id,
                user_id=user_id,
                vmcp_id=PUBLIC_VMCP_ID,
                original_filename=original_filename,
                filename=stored_filename,
                resource_name=resource.get("resource_name", original_filename),
                content=content_str,
                content_type=content_type,
                size=file_size,
                checksum=None,  # Could calculate MD5 if needed
                is_public=False,
                widget_id=None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            session.add(new_blob)
            session.flush()  # Get the blob ID without committing
            
            # Update resource with new blob ID (same format for both custom_resources and uploaded_files)
            updated_resource = {
                "id": blob_id,
                "original_filename": original_filename,
                "filename": stored_filename,
                "resource_name": resource.get("resource_name", original_filename),
                "content_type": content_type,
                "size": file_size,
                "vmcp_id": PUBLIC_VMCP_ID,
                "user_id": str(user_id),
                "created_at": datetime.now().isoformat(),
                "name": resource.get("name"),  # Preserve name if exists
                "uri": resource.get("uri"),  # Preserve uri if exists
                "description": resource.get("description")  # Preserve description if exists
            }
            updated_resources.append(updated_resource)
            
            logger.info(f"Uploaded blob {blob_id} for custom resource {original_filename}")
        
        # Update JSON data with updated resources
        # Frontend uses uploaded_files array for display, so populate both
        json_data["custom_resources"] = updated_resources
        json_data["uploaded_files"] = updated_resources  # Frontend displays from uploaded_files
        
        return True
        
    except Exception as e:
        logger.error(f"Error uploading custom resources: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def upload_to_public_registry(session, json_data: Dict[str, Any]) -> bool:
    """Upload 1xndemo to GlobalPublicVMCPRegistry"""
    try:
        # Ensure metadata exists
        if 'metadata' not in json_data:
            json_data['metadata'] = {}
        
        # Set type to 'demo' for consistency
        json_data['metadata']['type'] = 'demo'
        
        # Add required fields if missing
        if 'id' not in json_data:
            json_data['id'] = PUBLIC_VMCP_ID
        if 'user_id' not in json_data:
            json_data['user_id'] = '1'
        
        # Upload custom resource blobs to user's Blob table and update custom_resources (OSS only)
        if not upload_and_update_custom_resources_for_1xndemo(session, json_data):
            logger.warning("Failed to upload custom resources, continuing with original blob IDs")
        
        # Create VMCPConfig object from JSON data (now with updated custom_resources)
        vmcp_config = VMCPConfig.from_dict(json_data)
        
        # Convert to registry format
        vmcp_registry_config = vmcp_config.to_vmcp_registry_config()
        
        # Check if entry already exists
        existing = session.query(GlobalPublicVMCPRegistry).filter(
            GlobalPublicVMCPRegistry.public_vmcp_id == PUBLIC_VMCP_ID
        ).first()
        
        if existing:
            # Update existing entry
            existing.type = 'demo'
            existing.vmcp_registry_config = vmcp_registry_config.to_dict()
            existing.vmcp_config = vmcp_config.to_dict()
            logger.info(f"Updated existing public vMCP: {PUBLIC_VMCP_ID}")
        else:
            # Create new entry
            registry_entry = GlobalPublicVMCPRegistry(
                public_vmcp_id=PUBLIC_VMCP_ID,
                type='demo',
                vmcp_registry_config=vmcp_registry_config.to_dict(),
                vmcp_config=vmcp_config.to_dict()
            )
            session.add(registry_entry)
            logger.info(f"Created new public vMCP: {PUBLIC_VMCP_ID}")
        
        session.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error uploading to public registry: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        session.rollback()
        return False


async def import_to_private_vmcp(user_id: int = 1) -> bool:
    """Import 1xndemo from public registry to private VMCP table using the same import flow as install endpoint"""
    try:
        # Import the same functions used in install endpoint
        from vmcp.mcps.mcp_configmanager import MCPConfigManager
        from vmcp.mcps.mcp_client import MCPClientManager
        from vmcp.vmcps.router_typesafe import _process_servers_for_vmcp_import, _merge_vmcp_capabilities
        
        # Initialize managers (same as install endpoint)
        config_manager = MCPConfigManager(str(user_id))
        client_manager = MCPClientManager(config_manager)
        user_vmcp_manager = VMCPConfigManager(str(user_id))
        
        # Get public vMCP (same as install endpoint)
        public_vmcp_dict = user_vmcp_manager.get_public_vmcp(PUBLIC_VMCP_ID)
        if not public_vmcp_dict:
            logger.error(f"Public vMCP '{PUBLIC_VMCP_ID}' not found in registry")
            return False
        
        # Store original dict before converting to VMCPConfig (needed for copying tools/resources/prompts)
        original_public_vmcp_dict = public_vmcp_dict.copy()
        
        # Convert to VMCPConfig
        public_vmcp = VMCPConfig.from_dict(public_vmcp_dict)
        logger.info(f"Loaded public vMCP: {public_vmcp.name} (ID: {public_vmcp.id})")
        
        # Extract vmcp_config before processing servers (has complete tool details from vmcp_config column)
        original_vmcp_config = original_public_vmcp_dict.get('vmcp_config', {})
        
        # Process servers using shared function (same as install endpoint)
        # Use selected_servers from vmcp_config column (has complete tool details) instead of registry config
        selected_servers = original_vmcp_config.get('selected_servers', []) if original_vmcp_config else []
        processed_servers = await _process_servers_for_vmcp_import(
            vmcp_id=public_vmcp.id,
            selected_servers=selected_servers,
            config_manager=config_manager,
            client_manager=client_manager
        )
        
        # Ensure vmcp_config exists
        if public_vmcp.vmcp_config is None:
            public_vmcp.vmcp_config = {}
        
        # Update the vMCP config with processed servers (with actual statuses)
        public_vmcp.vmcp_config['selected_servers'] = processed_servers
        
        # Intelligently merge tools, resources, and prompts from public vMCP and user's existing servers
        # original_vmcp_config is already extracted above
        if original_vmcp_config:
            merged_capabilities = _merge_vmcp_capabilities(
                processed_servers=processed_servers,
                public_vmcp_config=original_vmcp_config,
                config_manager=config_manager
            )
            
            # Apply merged capabilities to vMCP config
            if merged_capabilities['selected_tools']:
                public_vmcp.vmcp_config['selected_tools'] = merged_capabilities['selected_tools']
                logger.info(f"   📋 Merged tools for {len(merged_capabilities['selected_tools'])} servers")
            
            if merged_capabilities['selected_resources']:
                public_vmcp.vmcp_config['selected_resources'] = merged_capabilities['selected_resources']
                logger.info(f"   📋 Merged resources for {len(merged_capabilities['selected_resources'])} servers")
            
            if merged_capabilities['selected_prompts']:
                public_vmcp.vmcp_config['selected_prompts'] = merged_capabilities['selected_prompts']
                logger.info(f"   📋 Merged prompts for {len(merged_capabilities['selected_prompts'])} servers")
            
            # Update total counts
            if public_vmcp.vmcp_config and 'selected_tools' in public_vmcp.vmcp_config:
                public_vmcp.total_tools = sum(len(tools) for tools in public_vmcp.vmcp_config['selected_tools'].values())
            if public_vmcp.vmcp_config and 'selected_resources' in public_vmcp.vmcp_config:
                public_vmcp.total_resources = sum(len(resources) for resources in public_vmcp.vmcp_config['selected_resources'].values())
            if public_vmcp.vmcp_config and 'selected_prompts' in public_vmcp.vmcp_config:
                public_vmcp.total_prompts = sum(len(prompts) for prompts in public_vmcp.vmcp_config['selected_prompts'].values())
        
        # Save the processed vMCP to private VMCP table (same as install endpoint)
        success = user_vmcp_manager.save_vmcp_config(public_vmcp)
        
        if success:
            logger.info(f"✅ Successfully imported {PUBLIC_VMCP_ID} to private VMCP table with processed servers and capabilities")
            return True
        else:
            logger.error(f"❌ Failed to import {PUBLIC_VMCP_ID} to private VMCP table")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error importing to private VMCP: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def main():
    """Main function"""
    console = Console()
    console.print("[cyan]🚀 Uploading and importing 1xndemo vMCP...[/cyan]")
    
    # Check if file exists
    if not XNDEMO_FILE.exists():
        console.print(f"[red]✗[/red] Error: 1xndemo_config.json not found at {XNDEMO_FILE}")
        return False
    
    # Load JSON data
    json_data = load_json_file(XNDEMO_FILE)
    if not json_data:
        console.print(f"[red]✗[/red] Error: Could not load 1xndemo_config.json")
        return False
    
    # Initialize database
    init_db()
    
    # Step 1: Upload to public registry
    console.print("[cyan]📦 Step 1: Uploading to public registry...[/cyan]")
    session = SessionLocal()
    try:
        if upload_to_public_registry(session, json_data):
            console.print("[green]✓[/green] Uploaded to public registry")
        else:
            console.print("[red]✗[/red] Failed to upload to public registry")
            return False
    finally:
        session.close()
    
    # Step 2: Import to private VMCP table
    console.print("[cyan]📥 Step 2: Importing to private VMCP table...[/cyan]")
    if asyncio.run(import_to_private_vmcp()):
        console.print("[green]✓[/green] Imported to private VMCP table")
    else:
        console.print("[red]✗[/red] Failed to import to private VMCP table")
        return False
    
    console.print("[green]🎉 1xndemo upload and import completed![/green]")
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🛑 Upload interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

