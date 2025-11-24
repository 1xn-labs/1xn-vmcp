# vMCP Core Architecture Redesign

## Executive Summary

This document outlines a plan to redesign the vMCP backend's core models and classes for better separation of concerns and optimized object instantiation. The current architecture creates too many objects eagerly, even when not required.

---

## Current Architecture Analysis

### Class Hierarchy & Lifecycle

| Class | Scope | Created When | Dependencies Created |
|-------|-------|--------------|---------------------|
| `VMCPServer` | Application (singleton) | Module load | `_vmcp_managers` dict |
| `VMCPSessionManager` | Application (singleton) | First HTTP request | Reference to `_vmcp_managers` |
| `UserContext` | Request | Every MCP request | `VMCPConfigManager` (eager) |
| `VMCPConfigManager` | Session | New session | `StorageBase`, `MCPConfigManager`, `MCPClientManager`, `Jinja2 Environment` |
| `MCPConfigManager` | Session | VMCP init | `StorageBase`, loads ALL servers |
| `MCPClientManager` | Session | VMCP init | `MCPAuthManager`, async infrastructure |

### Object Creation Flow (Current)

```
Request arrives with mcp-session-id header
    │
    ▼
VMCPServer.get_user_context_proxy_server()
    │
    ▼
Check session_id in _vmcp_managers cache
    │
    ├─► IF NOT in cache:
    │       │
    │       ▼
    │   Create UserContext (per-request)
    │       │
    │       ▼
    │   Create VMCPConfigManager (EAGER)
    │       ├── Create StorageBase
    │       ├── Create MCPConfigManager (EAGER)
    │       │       ├── Create StorageBase (DUPLICATE!)
    │       │       └── Load ALL servers from DB
    │       ├── Create MCPClientManager
    │       │       └── Create MCPAuthManager (often unused)
    │       └── Create Jinja2 Environment
    │       │
    │       ▼
    │   Cache in _vmcp_managers[session_id]
    │
    └─► IF in cache:
            └── Reuse cached VMCPConfigManager
```

---

## Problems Identified

### 1. Eager Object Creation

**Problem:** Objects created in `__init__` before they're needed.

| Location | Issue |
|----------|-------|
| `VMCPConfigManager.__init__` | Creates `MCPConfigManager` and `MCPClientManager` immediately |
| `MCPConfigManager.__init__` | Calls `load_mcp_servers()` - loads ALL servers from DB |
| `MCPClientManager.__init__` | Creates `MCPAuthManager` (only needed for 401 OAuth flows) |

**Impact:**
- User with 100 configured servers but vMCP using 5 → loads 100 `MCPServerConfig` objects
- Session that only lists tools still creates full connection infrastructure

### 2. Duplicate Storage Instances

**Problem:** `StorageBase` created multiple times per session.

```python
# In VMCPConfigManager.__init__
self.storage = StorageBase(user_id)

# In MCPConfigManager.__init__ (called from VMCPConfigManager)
self.storage = StorageBase(user_id)  # DUPLICATE!
```

**Impact:** Unnecessary memory allocation and potential DB connection overhead.

### 3. UserContext Mixes Concerns

**Problem:** `UserContext` combines user identity with vMCP management.

```python
# Current: oss_providers.py
class DummyUserContext:
    user_id: str
    username: str
    email: str
    token: str
    vmcp_name: str
    vmcp_config_manager: VMCPConfigManager  # Mixed concern!
```

**Impact:**
- Hard to test user identity separately from vMCP logic
- `UserContext` created per-request but `vmcp_config_manager` is session-scoped

### 4. No TTL-Based Cleanup

**Problem:** Session cleanup relies solely on explicit `on_session_end` callback.

```python
# vmcp_session_manager.py - only explicit cleanup
async def on_session_end(self, session_id: str):
    if session_id in self._vmcp_managers_ref:
        # cleanup...
        del self._vmcp_managers_ref[session_id]
```

**Impact:** If client crashes without proper session close, managers stay in memory indefinitely.

### 5. VMCPConfigManager Has Too Many Responsibilities

**Problem:** Single class handles config loading, tool execution, resource management, server management, template processing, and logging.

```python
# config_core.py - 1400+ lines with mixed responsibilities
class VMCPConfigManager:
    # Config management
    def load_vmcp_config(self) -> VMCPConfig
    def save_vmcp_config(self) -> bool
    def create_vmcp_config(self) -> str
    def update_vmcp_config(self) -> bool
    def delete_vmcp(self) -> Dict

    # Protocol operations (delegated but still here)
    async def tools_list(self) -> List[Tool]
    async def resources_list(self) -> List[Resource]
    async def prompts_list(self) -> List[Prompt]

    # Execution operations
    async def call_tool(self) -> Dict
    async def get_prompt(self) -> GetPromptResult
    async def get_resource(self) -> ReadResourceResult

    # Server management
    def install_public_vmcp(self) -> Dict
    def update_vmcp_server(self) -> None

    # Template processing
    def _is_jinja_template(self) -> bool
    def _preprocess_jinja_to_regex(self) -> str
    async def _parse_vmcp_text(self) -> Tuple

    # Logging
    async def log_vmcp_operation(self) -> None
```

---

## Proposed Redesign

### Design Principles

1. **Lazy Initialization**: Create objects only when first accessed
2. **Dependency Injection**: Pass shared instances instead of creating internally
3. **Single Responsibility**: Each class has one clear purpose
4. **Clear Lifecycle Scopes**: Application → Session → Request boundaries
5. **Minimal New Classes**: Refactor existing code, avoid adding complexity

### Phase 1: Lazy Initialization in Existing Classes

#### 1.1 VMCPConfigManager - Lazy Child Managers

```python
# config_core.py - BEFORE
class VMCPConfigManager:
    def __init__(self, user_id, vmcp_id, logging_config=None):
        self.storage = StorageBase(user_id)
        self.mcp_config_manager = MCPConfigManager(user_id)  # EAGER
        self.mcp_client_manager = MCPClientManager(self.mcp_config_manager)  # EAGER
        self.jinja_env = Environment(...)  # EAGER

# config_core.py - AFTER
class VMCPConfigManager:
    def __init__(self, user_id, vmcp_id, storage: StorageBase = None, logging_config=None):
        self._storage = storage  # Injected or lazy
        self.user_id = user_id
        self.vmcp_id = vmcp_id
        self._mcp_config_manager: Optional[MCPConfigManager] = None
        self._mcp_client_manager: Optional[MCPClientManager] = None
        self._jinja_env: Optional[Environment] = None
        self.logging_config = logging_config or {...}

    @property
    def storage(self) -> StorageBase:
        if self._storage is None:
            self._storage = StorageBase(self.user_id)
        return self._storage

    @property
    def mcp_config_manager(self) -> MCPConfigManager:
        if self._mcp_config_manager is None:
            self._mcp_config_manager = MCPConfigManager(self.user_id, storage=self.storage)
        return self._mcp_config_manager

    @property
    def mcp_client_manager(self) -> MCPClientManager:
        if self._mcp_client_manager is None:
            self._mcp_client_manager = MCPClientManager(self.mcp_config_manager)
        return self._mcp_client_manager

    @property
    def jinja_env(self) -> Environment:
        if self._jinja_env is None:
            self._jinja_env = Environment(...)
        return self._jinja_env
```

#### 1.2 MCPConfigManager - Lazy Server Loading

```python
# mcp_configmanager.py - BEFORE
class MCPConfigManager:
    def __init__(self, user_id):
        self.user_id = user_id
        self.storage = StorageBase(user_id)  # Creates new instance
        self._servers: Dict[str, MCPServerConfig] = {}
        self.load_mcp_servers()  # LOADS ALL SERVERS IMMEDIATELY

# mcp_configmanager.py - AFTER
class MCPConfigManager:
    def __init__(self, user_id: str, storage: StorageBase = None):
        self.user_id = user_id
        self._storage = storage  # Injected, shared with VMCPConfigManager
        self._servers: Optional[Dict[str, MCPServerConfig]] = None  # Lazy
        self._servers_loaded = False

    @property
    def storage(self) -> StorageBase:
        if self._storage is None:
            self._storage = StorageBase(self.user_id)
        return self._storage

    @property
    def servers(self) -> Dict[str, MCPServerConfig]:
        """Lazy load all servers on first access."""
        if not self._servers_loaded:
            self._servers = {}
            self._load_mcp_servers()
            self._servers_loaded = True
        return self._servers

    def get_server(self, server_id: str) -> Optional[MCPServerConfig]:
        """Get single server - uses cache if available, otherwise loads individually."""
        if self._servers_loaded and server_id in self._servers:
            return self._servers[server_id]
        # For non-bulk access, load single server
        return self._load_single_server(server_id)

    def _load_single_server(self, server_id: str) -> Optional[MCPServerConfig]:
        """Load a single server from storage without loading all."""
        server_data = self.storage.load_server(server_id)
        if server_data:
            config = MCPServerConfig.from_dict(server_data)
            if self._servers is not None:
                self._servers[server_id] = config
            return config
        return None
```

#### 1.3 MCPClientManager - Lazy Auth Manager

```python
# mcp_client.py - BEFORE
class MCPClientManager:
    def __init__(self, config_manager: MCPConfigManager = None):
        self.auth_manager = MCPAuthManager()  # ALWAYS CREATED
        self.config_manager = config_manager
        # ...

# mcp_client.py - AFTER
class MCPClientManager:
    def __init__(self, config_manager: MCPConfigManager = None):
        self._auth_manager: Optional[MCPAuthManager] = None  # Lazy
        self.config_manager = config_manager
        # ...

    @property
    def auth_manager(self) -> MCPAuthManager:
        """Lazy create auth manager - only needed for OAuth 401 flows."""
        if self._auth_manager is None:
            self._auth_manager = MCPAuthManager()
        return self._auth_manager
```

### Phase 2: Simplify UserContext

#### 2.1 Separate Identity from Session Management

```python
# oss_providers.py - BEFORE
class DummyUserContext:
    def __init__(self, user_id, user_email, username, token, vmcp_name):
        self.user_id = user_id
        self.user_email = user_email
        self.username = username
        self.token = token
        self.vmcp_name = vmcp_name

        # PROBLEM: Creates manager immediately
        self.vmcp_config_manager = VMCPConfigManager(
            user_id=int(user_id),
            vmcp_id=vmcp_name,
            logging_config={...}
        )

# oss_providers.py - AFTER
class DummyUserContext:
    """Request-scoped user identity. Does NOT own managers."""
    def __init__(self, user_id, user_email, username, token, vmcp_name):
        self.user_id = user_id
        self.user_email = user_email
        self.username = username
        self.token = token
        self.vmcp_name = vmcp_name

        # Manager is attached externally by VMCPServer, not created here
        self.vmcp_config_manager: Optional[VMCPConfigManager] = None

        # Additional attributes set by proxy_server
        self.vmcp_name_header: Optional[str] = None
        self.vmcp_username_header: Optional[str] = None
        self.client_id: Optional[str] = None
        self.client_name: Optional[str] = None
        self.agent_name: Optional[str] = None
```

### Phase 3: Add TTL-Based Cleanup

#### 3.1 Enhance VMCPServer with TTL Tracking

```python
# proxy_server.py - Add TTL tracking
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class SessionEntry:
    manager: VMCPConfigManager
    last_accessed: datetime

class VMCPServer(FastMCP):
    SESSION_TTL = timedelta(hours=1)  # Configurable

    def __init__(self, name: str):
        # ...
        self._vmcp_managers: dict[str, SessionEntry] = {}  # Changed type
        self._cleanup_task: Optional[asyncio.Task] = None

    async def _start_cleanup_task(self):
        """Background task to clean up expired sessions."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            await self._cleanup_expired_sessions()

    async def _cleanup_expired_sessions(self):
        """Remove sessions that haven't been accessed within TTL."""
        now = datetime.utcnow()
        expired = [
            session_id for session_id, entry in self._vmcp_managers.items()
            if now - entry.last_accessed > self.SESSION_TTL
        ]
        for session_id in expired:
            logger.info(f"[TTL CLEANUP] Removing expired session: {session_id}")
            entry = self._vmcp_managers.pop(session_id, None)
            if entry and entry.manager.mcp_client_manager:
                await entry.manager.mcp_client_manager.stop()

    def _get_or_create_manager(self, session_id: str, user_id: str, vmcp_id: str) -> VMCPConfigManager:
        """Get existing manager or create new one, updating last_accessed."""
        now = datetime.utcnow()

        if session_id in self._vmcp_managers:
            entry = self._vmcp_managers[session_id]
            entry.last_accessed = now  # Update access time
            return entry.manager

        # Create new manager with shared storage
        storage = StorageBase(user_id)
        manager = VMCPConfigManager(
            user_id=user_id,
            vmcp_id=vmcp_id,
            storage=storage
        )
        self._vmcp_managers[session_id] = SessionEntry(manager=manager, last_accessed=now)
        return manager
```

### Phase 4: Refactor get_user_context_proxy_server

```python
# proxy_server.py - Simplified
async def get_user_context_proxy_server(self):
    """Build request context with user identity and session manager."""
    try:
        # 1. Extract user identity from token
        request = get_http_request()
        token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        jwt_service = get_jwt_service()
        raw_info = jwt_service.extract_token_info(token)

        user_id = raw_info.get('user_id', '')
        username = raw_info.get('username', '')
        email = raw_info.get('email')

        # 2. Create lightweight UserContext (identity only)
        UserContext = get_user_context_class()
        user_context = UserContext(
            user_id=user_id,
            user_email=email,
            username=username,
            token=token,
            vmcp_name=request.headers.get('vmcp-name', 'unknown')
        )

        # 3. Get or create session manager (cached with TTL)
        session_id = request.headers.get('mcp-session-id')
        if not session_id:
            raise ValueError("No session ID provided in headers")

        vmcp_id = request.headers.get('vmcp-name', 'unknown')
        user_context.vmcp_config_manager = self._get_or_create_manager(
            session_id=session_id,
            user_id=user_id,
            vmcp_id=vmcp_id
        )

        # 4. Set downstream session for notifications (existing logic)
        try:
            server_session = self._mcp_server.request_context.session
            if user_context.vmcp_config_manager._mcp_client_manager:
                user_context.vmcp_config_manager.mcp_client_manager.set_downstream_session(server_session)
        except Exception as e:
            logger.debug(f"[NOTIFICATION] Could not set downstream session: {e}")

        # 5. Set additional context attributes
        user_context.agent_name = self._mcp_server.request_context.session.client_params.clientInfo.name
        user_context.vmcp_name_header = vmcp_id
        # ... other attributes

        return user_context

    except Exception as e:
        logger.error(f"Error building dependencies: {e}")
        return None
```

---

## Implementation Order

### Step 1: Lazy Initialization (Low Risk)
1. [ ] Add `@property` lazy getters to `VMCPConfigManager`
2. [ ] Add `@property` lazy getters to `MCPConfigManager`
3. [ ] Add `@property` lazy getter for `auth_manager` in `MCPClientManager`
4. [ ] Update all direct attribute access to use properties

### Step 2: Dependency Injection (Medium Risk)
1. [ ] Add `storage` parameter to `VMCPConfigManager.__init__`
2. [ ] Add `storage` parameter to `MCPConfigManager.__init__`
3. [ ] Update `VMCPServer` to create shared `StorageBase`
4. [ ] Update tests to inject mock storage

### Step 3: UserContext Simplification (Medium Risk)
1. [ ] Remove `vmcp_config_manager` creation from `DummyUserContext.__init__`
2. [ ] Update `get_user_context_proxy_server` to attach manager externally
3. [ ] Update any code that expects manager in UserContext init

### Step 4: TTL Cleanup (Low Risk)
1. [ ] Add `SessionEntry` dataclass
2. [ ] Change `_vmcp_managers` dict value type
3. [ ] Add `_cleanup_expired_sessions` method
4. [ ] Add background cleanup task in lifespan
5. [ ] Add `SESSION_TTL` configuration

### Step 5: Testing & Validation
1. [ ] Unit tests for lazy initialization
2. [ ] Integration tests for session lifecycle
3. [ ] Memory profiling before/after
4. [ ] Load testing with many concurrent sessions

---

## Expected Benefits

| Metric | Before | After |
|--------|--------|-------|
| Objects created on new session | 6+ (all eager) | 2 (UserContext + VMCPConfigManager shell) |
| StorageBase instances per session | 2 | 1 (shared) |
| Server configs loaded on session start | ALL | 0 (lazy) |
| MCPAuthManager created | Always | Only on 401 |
| Orphaned session cleanup | Never (until explicit close) | TTL-based (1 hour default) |

## Migration Notes

### Backward Compatibility

All changes are internal implementation details. External API remains unchanged:
- MCP protocol handlers work the same
- REST API endpoints work the same
- No changes to frontend integration

### Breaking Changes (Internal)

Code that directly accesses `_` prefixed attributes will need updates:
```python
# Before
manager.mcp_config_manager._servers

# After
manager.mcp_config_manager.servers  # Use property
```

### Configuration

Add to `settings.py`:
```python
# Session management
SESSION_TTL_HOURS: int = 1
SESSION_CLEANUP_INTERVAL_SECONDS: int = 300
```

---

## Open Questions

1. **Should we add max session limit?** Currently no limit on concurrent sessions.

2. **Should MCPConfigManager support partial server loading?** Current plan loads all on first `.servers` access. Could load per-vMCP selected servers only.

3. **Should we pool StorageBase connections?** Currently one instance per session. Could use connection pooling for better DB efficiency.

4. **Should VMCPConfigManager be split further?** It's still large after this refactor. Could extract:
   - `VMCPConfigRepository` - CRUD operations
   - `VMCPExecutor` - tool/prompt/resource execution
   - `VMCPTemplateEngine` - Jinja2 processing
