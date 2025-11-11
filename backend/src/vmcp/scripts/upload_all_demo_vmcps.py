#!/usr/bin/env python3
"""
Script to upload all JSON files from demo_vmcps folder to the global public vMCP registry table.

This script:
1. Scans the demo_vmcps directory for all .json files
2. Converts each JSON to VMCPConfig object
3. Sets metadata.type to 'demo' if not present
4. Uploads to the global_public_vmcp_registry database table
5. Uses file name (without .json) as public_vmcp_id

Usage:
    python -m vmcp.scripts.upload_all_demo_vmcps
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from vmcp.vmcps.models import VMCPConfig
from vmcp.storage.database import init_db, SessionLocal
from vmcp.storage.models import GlobalPublicVMCPRegistry
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upload_all_demo_vmcps")

# Get the package root directory
PACKAGE_ROOT = Path(__file__).parent.parent
DATA_DIR = PACKAGE_ROOT / "data"
DEMO_VMCPS_DIR = DATA_DIR / "demo_vmcps"


def load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse a JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return None


def ensure_demo_type(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure metadata.type is set to 'demo'"""
    if 'metadata' not in json_data:
        json_data['metadata'] = {}
    
    # Set type to 'demo' if not already set
    if json_data['metadata'].get('type') != 'demo':
        json_data['metadata']['type'] = 'demo'
    
    return json_data


def upload_vmcp_to_database(session, json_data: Dict[str, Any], file_name: str) -> bool:
    """Upload a single vMCP JSON to the database"""
    try:
        # Extract the public_vmcp_id from the file name (remove .json extension)
        public_vmcp_id = file_name.replace('.json', '')
        
        # Ensure type is set to 'demo'
        json_data = ensure_demo_type(json_data)
        
        # Add required fields if missing (id and user_id are required by VMCPConfig)
        if 'id' not in json_data:
            json_data['id'] = public_vmcp_id
        if 'user_id' not in json_data:
            # Use dummy user ID for OSS (user_id=1)
            json_data['user_id'] = '1'
        
        # Create VMCPConfig object from JSON data
        vmcp_config = VMCPConfig.from_dict(json_data)
        
        # Extract type from metadata
        vmcp_type = json_data.get('metadata', {}).get('type', 'demo')
        
        # Convert to registry format
        vmcp_registry_config = vmcp_config.to_vmcp_registry_config()
        
        # Check if entry already exists
        existing = session.query(GlobalPublicVMCPRegistry).filter(
            GlobalPublicVMCPRegistry.public_vmcp_id == public_vmcp_id
        ).first()
        
        if existing:
            # Update existing entry
            existing.type = vmcp_type
            existing.vmcp_registry_config = vmcp_registry_config.to_dict()
            existing.vmcp_config = vmcp_config.to_dict()
            logger.debug(f"Updated existing demo vMCP: {public_vmcp_id}")
        else:
            # Create new entry
            registry_entry = GlobalPublicVMCPRegistry(
                public_vmcp_id=public_vmcp_id,
                type=vmcp_type,
                vmcp_registry_config=vmcp_registry_config.to_dict(),
                vmcp_config=vmcp_config.to_dict()
            )
            session.add(registry_entry)
            logger.debug(f"Created new demo vMCP: {public_vmcp_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error processing {file_name}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def upload_all_demo_vmcps():
    """Upload all demo VMcPs from the demo_vmcps directory"""
    console = Console()
    
    # Check if directory exists
    if not DEMO_VMCPS_DIR.exists():
        console.print(f"[yellow]⚠[/yellow]  Demo VMcPs directory not found: {DEMO_VMCPS_DIR}")
        console.print("    Skipping demo VMcPs upload")
        return True  # Not an error, just nothing to upload
    
    # Find all JSON files
    json_files = list(DEMO_VMCPS_DIR.glob("*.json"))
    
    if not json_files:
        console.print(f"[yellow]⚠[/yellow]  No JSON files found in {DEMO_VMCPS_DIR}")
        console.print("    Skipping demo VMcPs upload")
        return True  # Not an error, just nothing to upload
    
    console.print(f"[cyan]Found {len(json_files)} demo VMcP file(s)[/cyan]")
    
    # Initialize database
    init_db()
    
    # Create database session
    session = SessionLocal()
    success_count = 0
    failed_count = 0
    
    try:
        # Upload each file with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            upload_task = progress.add_task(
                "[cyan]Loading demo VMcPs into registry...",
                total=len(json_files)
            )
            
            for json_file in json_files:
                progress.update(upload_task, description=f"[cyan]Processing {json_file.name}...")
                
                # Load JSON data
                json_data = load_json_file(json_file)
                if json_data is None:
                    failed_count += 1
                    progress.update(upload_task, advance=1)
                    continue
                
                # Upload to database
                if upload_vmcp_to_database(session, json_data, json_file.name):
                    success_count += 1
                else:
                    failed_count += 1
                
                progress.update(upload_task, advance=1)
        
        # Commit all changes
        session.commit()
        
        # Summary
        console.print(f"\n[green]✓[/green] Successfully loaded {success_count} demo VMcP(s)")
        if failed_count > 0:
            console.print(f"[yellow]⚠[/yellow]  Failed to load {failed_count} demo VMcP(s)")
        
        return success_count > 0
        
    except Exception as e:
        session.rollback()
        console.print(f"[red]✗[/red] Error uploading demo VMcPs: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
    finally:
        session.close()


def main():
    """Main function to upload all demo VMcPs"""
    console = Console()
    console.print("[cyan]🚀 Starting upload of demo VMcPs to public vMCP registry...[/cyan]")
    
    try:
        success = upload_all_demo_vmcps()
        if success:
            console.print("[green]🎉 Demo VMcPs upload completed![/green]")
            return True
        else:
            console.print("[yellow]⚠[/yellow]  No demo VMcPs were uploaded")
            return False
    except Exception as e:
        console.print(f"[red]💥 Unexpected error: {e}[/red]")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


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

