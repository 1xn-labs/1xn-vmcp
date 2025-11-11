#!/usr/bin/env python3
"""
Script to upload todo.json to the global public vMCP registry table.

This script:
1. Reads the todo.json file from data directory
2. Converts JSON to VMCPConfig object
3. Uploads to the global_public_vmcp_registry database table
4. Handles the type field extraction from metadata
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
from vmcp.storage.base import StorageBase
from vmcp.storage.database import init_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upload_demo_vmcp")

def load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse a JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return None

def extract_type_from_metadata(data: Dict[str, Any]) -> str:
    """Extract type from metadata, defaulting to 'vmcp' if not found"""
    metadata = data.get('metadata', {})
    return metadata.get('type', 'vmcp')

def upload_vmcp_to_database(storage_handler: StorageBase, json_data: Dict[str, Any], file_name: str) -> bool:
    """Upload a single vMCP JSON to the database"""
    try:
        # Extract the public_vmcp_id from the file name (remove .json extension)
        public_vmcp_id = file_name.replace('.json', '')
        
        # Create VMCPConfig object from JSON data
        vmcp_config = VMCPConfig.from_dict(json_data)
        
        # Extract type from metadata
        vmcp_type = extract_type_from_metadata(json_data)
        
        # Upload to global public vMCP registry using new method
        success = storage_handler.save_public_vmcp(vmcp_config)
        
        if success:
            logger.info(f"✅ Successfully uploaded {public_vmcp_id} (type: {vmcp_type})")
        else:
            logger.error(f"❌ Failed to upload {public_vmcp_id}")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error processing {file_name}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Main function to upload the todo.json file to database"""
    logger.info("🚀 Starting upload of todo.json to public vMCP registry...")
    
    # Initialize database
    init_db()
    
    # Define path to todo.json file
    todo_json_path = project_root / "vmcp" / "data" / "todo.json"
    logger.info(f"Looking for todo.json at: {todo_json_path}")
    
    if not todo_json_path.exists():
        logger.error(f"❌ File not found: {todo_json_path}")
        return False
    
    # Initialize storage handler
    storage_handler = StorageBase()
    
    logger.info(f"📁 Processing file: {todo_json_path}")
    
    # Load JSON data
    json_data = load_json_file(todo_json_path)
    if json_data is None:
        logger.error("❌ Failed to load todo.json")
        return False
    
    # Upload to database
    success = upload_vmcp_to_database(storage_handler, json_data, "todo.json")
    
    # Summary
    logger.info("=" * 60)
    logger.info("📊 UPLOAD SUMMARY")
    logger.info("=" * 60)
    
    if success:
        logger.info("✅ Successfully uploaded todo.json to public vMCP registry")
        logger.info("🎉 Upload completed successfully!")
        return True
    else:
        logger.error("❌ Failed to upload todo.json")
        logger.warning("⚠️  Upload failed")
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
