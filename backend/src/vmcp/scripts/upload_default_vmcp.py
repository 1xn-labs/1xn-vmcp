#!/usr/bin/env python3
"""
Script to upload default VMCP configuration to all users.
This script reads the 1xndemo_config.json file and uploads it as a default VMCP
for all users in the database.

Usage:
    python -m vmcp.scripts.upload_default_vmcp
"""

import json
import sys
import base64
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Get the package root directory
PACKAGE_ROOT = Path(__file__).parent.parent
DATA_DIR = PACKAGE_ROOT / "data"
JSON_FILE = DATA_DIR / "1xndemo_config.json"


def load_vmcp_config(json_file_path: Path) -> Optional[Dict[str, Any]]:
    """Load VMCP configuration from JSON file"""
    if not json_file_path.exists():
        return None
    
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    return data


def upload_logo_file(user_id: int, vmcp_id: str, session) -> Optional[str]:
    """Upload the logo file as a blob and return the blob ID"""
    from vmcp.storage.models import Blob
    
    try:
        # Find the logo file
        logo_file = DATA_DIR / "1xn_logo-med-size.png"
        
        if not logo_file.exists():
            # Try alternative paths
            import os
            cwd = Path(os.getcwd())
            alt_path = cwd / "oss" / "backend" / "src" / "vmcp" / "data" / "1xn_logo-med-size.png"
            if alt_path.exists():
                logo_file = alt_path
            else:
                return None
        
        # Read file content
        with open(logo_file, 'rb') as f:
            file_content = f.read()
        
        file_size = len(file_content)
        original_filename = "1xn_logo-med-size.png"
        normalized_name = "1xn_logo-med-size"
        
        # Generate unique blob ID
        blob_id = str(uuid.uuid4())
        
        # Create stored filename
        stored_filename = f"{normalized_name}_{blob_id}.png"
        
        # Encode binary content as base64
        content_str = base64.b64encode(file_content).decode('utf-8')
        
        # Create blob record
        new_blob = Blob(
            id=blob_id,
            user_id=user_id,
            original_filename=original_filename,
            filename=stored_filename,
            resource_name=f"file://{normalized_name}",
            content=content_str,
            content_type="image/png",
            size=file_size,
            vmcp_id=vmcp_id,
            widget_id=None,
            is_public=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        session.add(new_blob)
        session.flush()  # Get the blob ID without committing
        
        return blob_id
    except Exception as e:
        # Silently fail if logo upload fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to upload logo file: {e}")
        return None


def upload_vmcp_to_database(vmcp_config: Dict[str, Any], user_id: int):
    """Upload VMCP configuration to the database for a specific user"""
    from vmcp.storage.database import SessionLocal, init_db
    from vmcp.storage.models import VMCP

    # Ensure tables exist
    init_db()

    session = SessionLocal()
    try:
        # Calculate totals from the config
        # Get vmcp_config nested dict (contains selected_tools, selected_resources, etc.)
        vmcp_config_data = vmcp_config.get("vmcp_config", {})
        
        # Get custom arrays
        custom_tools = vmcp_config.get("custom_tools", [])
        custom_prompts = vmcp_config.get("custom_prompts", [])
        custom_resources = vmcp_config.get("custom_resources", [])
        custom_resource_templates = vmcp_config.get("custom_resource_templates", [])
        
        # Get selected mappings from vmcp_config
        selected_tools = vmcp_config_data.get("selected_tools", {}) or {}
        selected_resources = vmcp_config_data.get("selected_resources", {}) or {}
        selected_prompts = vmcp_config_data.get("selected_prompts", {}) or {}
        selected_resource_templates = vmcp_config_data.get("selected_resource_templates", {}) or {}
        
        # Calculate totals
        total_tools = len(custom_tools) + sum(
            len(x) for x in selected_tools.values() if isinstance(x, list)
        )
        total_resources = len(custom_resources) + sum(
            len(x) for x in selected_resources.values() if isinstance(x, list)
        )
        total_resource_templates = len(custom_resource_templates) + sum(
            len(x) for x in selected_resource_templates.values() if isinstance(x, list)
        )
        total_prompts = len(custom_prompts) + sum(
            len(x) for x in selected_prompts.values() if isinstance(x, list)
        )
        
        # Add totals to the config dict
        vmcp_config["total_tools"] = total_tools
        vmcp_config["total_resources"] = total_resources
        vmcp_config["total_resource_templates"] = total_resource_templates
        vmcp_config["total_prompts"] = total_prompts
        
        # Extract VMCP ID from config (e.g., "1xndemo" from metadata or name)
        vmcp_id = vmcp_config.get("name", "1xndemo")
        
        # Upload logo file as blob
        logo_blob_id = upload_logo_file(user_id, vmcp_id, session)
        
        # Update custom_resources to reference the uploaded logo
        if logo_blob_id:
            # Check if custom_resources already has the logo entry
            custom_resources = vmcp_config.get("custom_resources", [])
            
            # Remove any existing logo entries
            custom_resources = [r for r in custom_resources if r.get("original_filename") != "1xn_logo-med-size.png"]
            
            # Get the actual file size from the blob
            from vmcp.storage.models import Blob
            blob = session.query(Blob).filter(Blob.id == logo_blob_id).first()
            file_size = blob.size if blob else 14107
            
            # Add new logo entry
            logo_resource = {
                "id": logo_blob_id,
                "original_filename": "1xn_logo-med-size.png",
                "filename": f"1xn_logo-med-size_{logo_blob_id}.png",
                "resource_name": "1xn_logo-med-size.png",
                "content_type": "image/png",
                "size": file_size,
                "vmcp_id": vmcp_id,
                "user_id": str(user_id),
                "created_at": datetime.now().isoformat()
            }
            custom_resources.append(logo_resource)
            vmcp_config["custom_resources"] = custom_resources
        
        # Check if VMCP already exists for this user
        existing_vmcp = session.query(VMCP).filter(
            VMCP.user_id == user_id,
            VMCP.vmcp_id == vmcp_id
        ).first()

        if existing_vmcp:
            # Update existing VMCP
            existing_vmcp.name = vmcp_config.get("name", vmcp_id)
            existing_vmcp.description = vmcp_config.get("description")
            existing_vmcp.vmcp_config = vmcp_config
            session.commit()
            return True, "updated"
        else:
            # Create new VMCP
            vmcp_entry = VMCP(
                id=f"{user_id}_{vmcp_id}",
                user_id=user_id,
                vmcp_id=vmcp_id,
                name=vmcp_config.get("name", vmcp_id),
                description=vmcp_config.get("description"),
                vmcp_config=vmcp_config,
            )
            session.add(vmcp_entry)
            session.commit()
            return True, "created"

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def upload_vmcp_to_all_users(vmcp_config: Dict[str, Any]):
    """Upload VMCP configuration to all users in the database"""
    from vmcp.storage.database import SessionLocal, init_db
    from vmcp.storage.models import User
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.console import Console

    # Ensure tables exist
    init_db()

    session = SessionLocal()
    console = Console()
    
    try:
        # Get all users
        users = session.query(User).all()
        
        if not users:
            console.print("[yellow]⚠[/yellow] No users found in database. Skipping VMCP upload.")
            return

        console.print(f"[cyan]Found {len(users)} user(s) in database[/cyan]")

        # Upload VMCP for each user with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            upload_task = progress.add_task(
                "[cyan]Uploading default VMCP to users...",
                total=len(users)
            )

            success_count = 0
            failed_count = 0
            created_count = 0
            updated_count = 0

            for user in users:
                try:
                    success, action = upload_vmcp_to_database(vmcp_config, user.id)
                    if success:
                        success_count += 1
                        if action == "created":
                            created_count += 1
                        else:
                            updated_count += 1
                    progress.update(upload_task, advance=1)
                except Exception as e:
                    failed_count += 1
                    progress.console.print(f"[yellow]⚠[/yellow] Error processing user {user.id}: {e}")
                    progress.update(upload_task, advance=1)
                    continue

        # Summary
        console.print(f"[green]✓[/green] Successfully processed {success_count}/{len(users)} user(s)")
        if created_count > 0:
            console.print(f"   [green]+[/green] Created: {created_count}")
        if updated_count > 0:
            console.print(f"   [blue]~[/blue] Updated: {updated_count}")
        if failed_count > 0:
            console.print(f"[yellow]⚠[/yellow] {failed_count} user(s) failed to process")

    except Exception as e:
        console.print(f"[red]✗[/red] Database error: {e}")
        raise
    finally:
        session.close()


def main():
    """Main function"""
    from rich.console import Console

    console = Console()

    # Check if JSON file exists
    if not JSON_FILE.exists():
        console.print(f"[red]✗[/red] Error: JSON file not found at {JSON_FILE}")
        sys.exit(1)

    # Load VMCP config
    vmcp_config = load_vmcp_config(JSON_FILE)
    if not vmcp_config:
        console.print(f"[red]✗[/red] Error: Could not load VMCP config from {JSON_FILE}")
        sys.exit(1)

    console.print(f"[cyan]Loaded VMCP config: {vmcp_config.get('name', 'Unknown')}[/cyan]")
    console.print(f"   Description: {vmcp_config.get('description', 'N/A')}")

    # Upload to all users
    upload_vmcp_to_all_users(vmcp_config)


if __name__ == "__main__":
    main()

