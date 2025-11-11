"""
OAuth State Manager for MCP servers

Handles storage and retrieval of OAuth state mappings to associate
OAuth callbacks with specific users and servers.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from vmcp.storage.base import StorageBase

logger = logging.getLogger(__name__)

class OAuthStateManager:
    """
    Manages OAuth state storage for MCP server authentication
    Stores mappings between OAuth state tokens and user/server information
    to handle OAuth callbacks properly.
    """
    
    def __init__(self):
        
        # State expiration time (1 hour)
        self.state_expiry_seconds = 3600
        self.storage_handler = StorageBase()
        
        logger.info(f"🔧 OAuthStateManager initialized")
    
    def create_oauth_state(self, server_name: str, mcp_state: str, user_id: str, oauth_config: Dict[str, Any] = None) -> bool:
        """
        Create an OAuth state mapping
        
        Args:
            user_id: User ID
            server_name: MCP server name
            mcp_state: OAuth state token from MCP server
            oauth_config: OAuth configuration data (token_url, code_verifier, etc.)
            
        Returns:
            bool: True if state was created successfully
        """
        try:
            
            state_data = {
                "user_id": user_id,
                "server_name": server_name,
                "mcp_state": mcp_state,
                "created_at": time.time(),
                "expires_at": time.time() + self.state_expiry_seconds
            }
            
            # Add OAuth configuration data if provided
            if oauth_config:
                state_data.update(oauth_config)
            
            # Create state file using mcp_state as filename
            self.storage_handler.save_oauth_state(state_data)
            
            logger.info(f"✅ Created OAuth state for user {user_id}, server {server_name}, state: {mcp_state[:8]}...")
            logger.info(f"🔍 Stored OAuth config - code_verifier: {state_data.get('code_verifier', 'NOT_FOUND')[:10] if state_data.get('code_verifier') else 'NOT_FOUND'}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create OAuth state: {e}")
            return False
    
    def get_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve OAuth state mapping
        
        Args:
            state: OAuth state token
            
        Returns:
            dict: State data if valid and not expired, None otherwise
        """
        try:
            state_data = self.storage_handler.get_oauth_state(state)
            
            # Check if state is expired
            if time.time() > state_data.get("expires_at", 0):
                logger.warning(f"⚠️ OAuth state expired: {state[:8]}...")
                self.cleanup_oauth_state(state)
                return None
            
            logger.info(f"✅ Retrieved OAuth state for user {state_data.get('user_id')}, server {state_data.get('server_name')}")
            logger.info(f"🔍 Retrieved OAuth config - code_verifier: {state_data.get('code_verifier', 'NOT_FOUND')[:10] if state_data.get('code_verifier') else 'NOT_FOUND'}...")
            return state_data
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve OAuth state {state[:8]}...: {e}")
            return None
    
    def cleanup_oauth_state(self, state: str) -> bool:
        """
        Clean up OAuth state after use
        
        Args:
            state: OAuth state token
            
        Returns:
            bool: True if state was cleaned up successfully
        """
        try:
            self.storage_handler.delete_oauth_state(state)
            logger.info(f"🧹 Cleaned up OAuth state: {state[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup OAuth state {state[:8]}...: {e}")
            return False
    
    def cleanup_expired_states(self) -> int:
        """
        Clean up all expired OAuth states
        
        Returns:
            int: Number of expired states cleaned up
        """
        try:
            cleaned_count = 0
            current_time = time.time()
            
            for state_data in self.storage_handler.get_oauth_states():
                try:
                    
                    if current_time > state_data.get("expires_at", 0):
                        self.storage_handler.delete_oauth_state(state_data.get("mcp_state"))
                        cleaned_count += 1
                        logger.debug(f"🧹 Cleaned up expired OAuth state: {state_data.get('mcp_state')[:8]}...")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error processing state file {state_data.get('mcp_state')}: {e}")
                    # Remove corrupted state files
                    try:
                        self.storage_handler.delete_oauth_state(state_data.get("mcp_state"))
                        cleaned_count += 1
                    except:
                        pass
            
            if cleaned_count > 0:
                logger.info(f"🧹 Cleaned up {cleaned_count} expired OAuth states")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup expired OAuth states: {e}")
            return 0
    
    def get_active_states_count(self) -> int:
        """
        Get count of active (non-expired) OAuth states
        
        Returns:
            int: Number of active OAuth states
        """
        try:
            active_count = 0
            current_time = time.time()
            
            for state_data in self.storage_handler.get_oauth_states():
                try:
                    
                    if current_time <= state_data.get("expires_at", 0):
                        active_count += 1
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error reading state file {state_data.get('mcp_state')}: {e}")
            
            return active_count
            
        except Exception as e:
            logger.error(f"❌ Failed to count active OAuth states: {e}")
            return 0 