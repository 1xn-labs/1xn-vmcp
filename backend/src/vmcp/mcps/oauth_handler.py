from fastapi import APIRouter, Request, Depends
from vmcp.storage.dummy_user import get_user_context
from vmcp.utilities.logging.config import setup_logging
from fastapi import Query

logger = setup_logging("OAUTH_HANDLER")

router = APIRouter()

@router.get("/otherservers/oauth/callback")
async def oauth_callback_page(code: str, state: str):
    """Handle OAuth callback GET request and show success page"""
    logger.info(f"🔗 OAuth callback received:")
    logger.info(f"   Full code: '{code}'")
    logger.info(f"   Code length: {len(code)}")
    logger.info(f"   Full state: '{state}'")
    logger.info(f"   State length: {len(state)}")
    # logger.info(f"   Chat Client Callback: '{chat_client_callback}'")
    # logger.info(f"   Conversation ID: '{conversation_id}'")
    
    # URL decode the code to see the actual value
    import urllib.parse
    decoded_code = urllib.parse.unquote(code)
    logger.info(f"   URL decoded code: '{decoded_code}'")
    logger.info(f"   URL decoded code length: {len(decoded_code)}")
    
    try:
        # Get OAuth state manager to retrieve user context from state
        from vmcp.mcps.oauth_state_manager import OAuthStateManager
        from vmcp.storage.base import StorageBase
        
        # Use global storage handler to find OAuth state across all users
        global_storage = StorageBase()  # No user_id = global mode
        state_data = global_storage.get_oauth_state(state)
        
        if not state_data:
            logger.error(f"❌ Could not find OAuth state for state: {state[:8]}...")
            from fastapi.responses import HTMLResponse
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>OAuth Error</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>Authentication Failed</h1>
                <p>Could not find OAuth state. Please try again.</p>
                <button onclick="window.close()">Close Window</button>
            </body>
            </html>
            """
            return HTMLResponse(content=error_html, status_code=400)
        
        user_id = state_data["user_id"]
        server_name = state_data["server_name"]
        conversation_id = state_data.get("conversation_id")
        chat_client_callback_url = state_data.get("chat_client_callback_url")
        
        # Now create user-specific OAuth state manager for cleanup
        oauth_state_manager = OAuthStateManager()
        
        # Clean up the OAuth state after successful retrieval
        oauth_state_manager.cleanup_oauth_state(state)
        
        logger.info(f"👤 OAuth callback for user: {user_id}, server: {server_name}")
        
        # Create user context and managers
        from vmcp.mcps.models import MCPConnectionStatus
        from vmcp.mcps.mcp_configmanager import MCPConfigManager
        from vmcp.mcps.mcp_client import MCPClientManager
        config_manager = MCPConfigManager(user_id)
        client_manager = MCPClientManager(config_manager)
        
        # Handle OAuth callback
        logger.info(f"🔄 Processing OAuth callback...")
        
        # Debug: Log the complete state data
        logger.info(f"🔍 Complete state data:")
        logger.info(f"   State data keys: {list(state_data.keys())}")
        for key, value in state_data.items():
            if key == 'code_verifier':
                logger.info(f"   {key}: '{value}...' (length: {len(value)})")
            else:
                logger.info(f"   {key}: '{value}'")
        
        # Extract OAuth configuration from state data
        oauth_config = {
            'token_url': state_data.get('token_url'),
            'code_verifier': state_data.get('code_verifier'),
            'callback_url': state_data.get('callback_url'),
            'client_id': state_data.get('client_id'),
            'user_id': user_id,
            'client_secret': state_data.get('client_secret')
        }
        
        # Debug: Log the OAuth configuration
        logger.info(f"🔍 OAuth config - token_url: {oauth_config.get('token_url')}")
        logger.info(f"🔍 OAuth config - code_verifier: {oauth_config.get('code_verifier', 'NOT_FOUND')[:10] if oauth_config.get('code_verifier') else 'NOT_FOUND'}...")
        logger.info(f"🔍 OAuth config - callback_url: {oauth_config.get('callback_url')}")
        logger.info(f"🔍 OAuth config - client_id: {oauth_config.get('client_id')}")
        logger.info(f"🔍 OAuth config - client_secret: {oauth_config.get('client_secret')}")
        
        # Pass OAuth configuration to the callback handler
        result = await client_manager.auth_manager.handle_oauth_callback(code, state, oauth_config)
        logger.info(f"📊 OAuth callback result: {result}")
        
        if result.get('access_token') is None:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ OAuth callback failed: {error_msg}")
            # Return error page
            from fastapi.responses import HTMLResponse
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>OAuth Error</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>Authentication Failed</h1>
                <p>OAuth callback failed: {error_msg}</p>
                <button onclick="window.close()">Close Window</button>
            </body>
            </html>
            """
            return HTMLResponse(content=error_html, status_code=400)
        
        if result.get('access_token') is not None:
            logger.info(f"✅ OAuth successful for server: {server_name}")
            
            # Update server config with tokens
            if server_name and config_manager:
                server_config = config_manager.get_server(server_name)
                logger.info(f"🔍 Found server config: {server_config is not None}")
                if server_config:
                    logger.info(f"🔍 Server config auth: {server_config.auth is not None}")
                    logger.info(f"🔍 Server config auth type: {server_config.auth.type if server_config.auth else 'None'}")
                
                if server_config:
                    # Create auth config if it doesn't exist
                    if not server_config.auth:
                        logger.info(f"🔧 Creating OAuth auth config for {server_name}")
                        from vmcp.mcps.models import MCPAuthConfig
                        server_config.auth = MCPAuthConfig(
                            type="oauth",
                            client_id=result.get('client_id', '1xn-cli'),
                            access_token=result.get('access_token'),
                            refresh_token=result.get('refresh_token')
                        )
                        if result.get('expires_in'):
                            from datetime import datetime, timedelta
                            server_config.auth.expires_at = datetime.now() + timedelta(seconds=result['expires_in'])
                        logger.info(f"✅ Created OAuth auth config for {server_name}")
                    else:
                        # Update existing auth config
                        logger.info(f"🔑 Updating auth tokens for {server_name}")
                        server_config.auth.access_token = result.get('access_token')
                        server_config.auth.refresh_token = result.get('refresh_token')
                        if result.get('expires_in'):
                            from datetime import datetime, timedelta
                            server_config.auth.expires_at = datetime.now() + timedelta(seconds=result['expires_in'])
                    
                    # Save the updated config
                    config_manager.update_server_config(server_name, server_config)
                    logger.info(f"💾 Saved updated config for {server_name}")
                    
                    # Try to connect to the server now that we have tokens
                    try:
                        logger.info(f"🔄 Attempting to connect to {server_name} after OAuth success")
                        success = await client_manager.ping_server(server_config.server_id)
                        if success:
                            logger.info(f"✅ Successfully connected to {server_name} after OAuth")
                            # Update status to connected
                            server_config.status = MCPConnectionStatus.CONNECTED
                            server_config.last_error = None
                            config_manager.update_server_status(server_name, MCPConnectionStatus.CONNECTED)
                            logger.info(f"💾 Updated {server_name} status to CONNECTED")
                        else:
                            logger.warning(f"❌ Failed to connect to {server_name} after OAuth")

                        # Discover capabilities
                        try:
                            capabilities = await client_manager.discover_capabilities(server_config.server_id)
                        except Exception as e:
                            logger.error(f"   ❌ Error discovering capabilities for server {server_config.server_id}: {e}")
                            capabilities = None

            
                        if capabilities:
                            # Update server config with discovered capabilities
                            if capabilities.get('tools',[]):
                                server_config.tools = capabilities.get('tools', [])
                            if capabilities.get('resources',[]):
                                server_config.resources = capabilities.get('resources', [])
                            if capabilities.get('prompts',[]):
                                server_config.prompts = capabilities.get('prompts', [])
                            if capabilities.get('tool_details',[]):
                                server_config.tool_details = capabilities.get('tool_details', [])
                            if capabilities.get('resource_details',[]):
                                server_config.resource_details = capabilities.get('resource_details', [])
                            if capabilities.get('resource_templates',[]):
                                server_config.resource_templates = capabilities.get('resource_templates', [])
                            if capabilities.get('resource_template_details',[]):
                                server_config.resource_template_details = capabilities.get('resource_template_details', [])
                            if capabilities.get('prompt_details',[]):
                                server_config.prompt_details = capabilities.get('prompt_details', [])
                    
                            server_config.capabilities = {
                                "tools": bool(server_config.tools and len(server_config.tools) > 0),
                                "resources": bool(server_config.resources and len(server_config.resources) > 0),
                                "prompts": bool(server_config.prompts and len(server_config.prompts) > 0)
                            }

                
                            logger.info(f"   ✅ Successfully tried to discover capabilities for server '{server_config.server_id} Current status {server_config.status.value}'")
                
                            # Save updated server config
                            config_manager.update_server_config(server_config.server_id, server_config)
                    except Exception as e:
                        logger.warning(f"Failed to auto-connect after OAuth for {server_name}: {traceback.format_exc()}")
                        logger.warning(f"Failed to auto-connect after OAuth for {server_name}: {e}")
            
            # Dynamic client notification
            if chat_client_callback_url and conversation_id:
                logger.info(f"🔄 Notifying client at: {chat_client_callback_url}")
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            chat_client_callback_url,
                            json={
                                "conversation_id": conversation_id,
                                "server_name": server_name,
                                "auth_status": "completed",
                                "user_id": state_data['user_id']
                            },
                            headers={"Content-Type": "application/json"},
                            timeout=10.0
                        )
                        
                        if response.status_code == 200:
                            logger.info(f"✅ Successfully notified client about auth completion")
                        else:
                            logger.error(f"❌ Failed to notify client: {response.status_code} - {response.text}")
                            
                except Exception as e:
                    logger.error(f"❌ Error notifying client about auth completion: {e}")
            
            # Clean up OAuth state
            oauth_state_manager.cleanup_oauth_state(state)
            
            # Return HTML success page
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>OAuth Success</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>Authentication Successful</h1>
                <p>Successfully authenticated with {server_name}</p>
                <button onclick="window.close()">Close Window</button>
            </body>
            </html>
            """
            
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=html_content, status_code=200)
            
        else:
            # Return error page
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>OAuth Error</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                        color: white;
                        margin: 0;
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .error-card {{
                        background: rgba(255, 255, 255, 0.1);
                        backdrop-filter: blur(10px);
                        border-radius: 20px;
                        padding: 40px;
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                        border: 1px solid rgba(255, 255, 255, 0.2);
                        max-width: 500px;
                    }}
                    .error-icon {{
                        font-size: 4rem;
                        margin-bottom: 20px;
                        color: #fca5a5;
                    }}
                    h1 {{
                        margin: 0 0 20px 0;
                        font-size: 2rem;
                    }}
                    p {{
                        margin: 0 0 30px 0;
                        font-size: 1.1rem;
                        opacity: 0.9;
                    }}
                    .close-btn {{
                        background: #ef4444;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-size: 1rem;
                        cursor: pointer;
                        transition: background 0.3s;
                    }}
                    .close-btn:hover {{
                        background: #dc2626;
                    }}
                </style>
            </head>
            <body>
                <div class="error-card">
                    <div class="error-icon">❌</div>
                    <h1>Authentication Failed</h1>
                    <p>Error: {result.get('error', 'Unknown error')}</p>
                    <p>Please try again.</p>
                    <button class="close-btn" onclick="window.close()">Close Window</button>
                </div>
            </body>
            </html>
            """
            
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=html_content, status_code=400)
            
    except Exception as e:
        logger.error(f"OAuth callback processing failed: {e}")
        # Return error page
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Error</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: white;
                    margin: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .error-card {{
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 40px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    max-width: 500px;
                }}
                .error-icon {{
                    font-size: 4rem;
                    margin-bottom: 20px;
                    color: #fca5a5;
                }}
                h1 {{
                    margin: 0 0 20px 0;
                    font-size: 2rem;
                }}
                p {{
                    margin: 0 0 30px 0;
                    font-size: 1.1rem;
                    opacity: 0.9;
                }}
                .close-btn {{
                    background: #ef4444;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: background 0.3s;
                }}
                .close-btn:hover {{
                    background: #dc2626;
                }}
            </style>
        </head>
        <body>
            <div class="error-card">
                <div class="error-icon">❌</div>
                <h1>Authentication Failed</h1>
                <p>Error: {str(e)}</p>
                <p>Please try again.</p>
                <button class="close-btn" onclick="window.close()">Close Window</button>
            </div>
        </body>
        </html>
        """
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content, status_code=500)