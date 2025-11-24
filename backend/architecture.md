# vMCP Server Architecture

## Module Structure

```
vmcp/server/
├── vmcp_server.py          # FastAPI application (HTTP server, routing)
├── vmcp_mcp_server.py      # VMCPServer class (MCP protocol handling)
├── vmcp_session_manager.py # Session lifecycle & VMCPConfigManager ownership
└── __init__.py             # Exports: VMCPServer, app, vmcp, create_app
```

## Core Components

### VMCPServer (vmcp_mcp_server.py)
MCP protocol handler extending FastMCP.

**Responsibilities:**
- MCP protocol operations (tools, resources, prompts)
- Request context extraction (user identity, headers)
- Delegates session/manager lifecycle to VMCPSessionManager

### VMCPSessionManager (vmcp_session_manager.py)
Session lifecycle manager extending StreamableHTTPSessionManager.

**Responsibilities:**
- Creates and caches `VMCPConfigManager` per session
- Session lifecycle hooks (`on_session_start`, `on_session_end`)
- MCP connection cleanup when sessions end
- TTL-based session expiration for disconnected clients

**Key Methods:**
- `get_manager(session_id)` → Get cached VMCPConfigManager (updates last_accessed)
- `create_manager(session_id, user_id, vmcp_name)` → Create & cache new manager

### vmcp_server.py (FastAPI Application)
HTTP server and API routing.

**Responsibilities:**
- FastAPI app creation and configuration
- CORS, middleware, tracing setup
- Router mounting (MCP, vMCP, OAuth, stats)
- Frontend SPA serving

### UserContext (oss_providers.py)
Pure identity container - does NOT create VMCPConfigManager.

**Attributes:** user_id, username, email, token, vmcp_name, vmcp_config_manager (set externally)

## Request Flow

```
HTTP Request → FastAPI (vmcp_server.py)
    │
    ▼
VMCPServer.get_user_context_vmcp_server()
    │
    ├─► Extract user identity from token
    ├─► Create lightweight UserContext (identity only)
    ├─► session_manager.get_manager(session_id)
    │       └─► Returns cached VMCPConfigManager or None
    ├─► If None: session_manager.create_manager(session_id, user_id, vmcp_name)
    │       └─► Creates, caches, and returns new VMCPConfigManager
    └─► Attach manager to UserContext
    │
    ▼
Protocol Handler (proxy_list_tools, proxy_call_tool, etc.)
    │
    ▼
VMCPConfigManager → MCPClientManager → Upstream MCP Servers
```

## Session Lifecycle

```
Session Start (new mcp-session-id header)
    │
    ▼
VMCPSessionManager.on_session_start(session_id)
    │
    ▼
First request: create_manager(session_id, user_id, vmcp_name)
    │
    ▼
Subsequent requests: get_manager(session_id) → cached manager
    │
    ▼
Session End (client disconnect, crash, or shutdown)
    │
    ▼
VMCPSessionManager.on_session_end(session_id)
    ├─► mcp_client_manager.stop() → cleanup all MCP connections
    └─► Remove manager from cache
```

## Design Principles

1. **Single Responsibility**: Each class has one clear purpose
2. **Session Manager Owns State**: VMCPSessionManager owns all session state
3. **Identity vs State Separation**: UserContext = identity, SessionManager = session state
4. **Lazy Initialization**: Managers created on first request, not eagerly
