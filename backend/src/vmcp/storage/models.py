"""
Database models for vMCP OSS version.

Simplified models without authentication - uses a single dummy user for all operations.
Only includes essential tables: User (dummy), MCP servers, VMCPs, stats, and logs.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# SQLite-compatible JSON type
class JSONType(TypeDecorator):
    """Platform-independent JSON type.

    Uses JSON for PostgreSQL, Text for SQLite.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            try:
                return json.dumps(value, default=self._json_serializer)
            except (TypeError, ValueError) as e:
                # Log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"JSON serialization error: {e}, Value type: {type(value)}")
                logger.error(f"Problematic value: {value}")
                raise
        return value
    
    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for objects not serializable by default json module."""
        from datetime import datetime, date
        from enum import Enum
        from pydantic import BaseModel
        
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, BaseModel):
            return obj.model_dump(mode='python')
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'AnyUrl':
            return str(obj)
        else:
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def process_result_value(self, value, dialect):
        if value is not None:
            # PostgreSQL JSONB columns are already deserialized by the driver
            # SQLite stores JSON as TEXT and needs parsing
            if isinstance(value, (dict, list)):
                return value
            return json.loads(value)
        return value


class User(Base):
    """
    Dummy user model for OSS version.

    In OSS, there's always a single local user. This simplifies the codebase
    while keeping the API structure consistent for future auth extensions.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    mcp_servers = relationship("MCPServer", back_populates="user", cascade="all, delete-orphan")
    vmcps = relationship("VMCP", back_populates="user", cascade="all, delete-orphan")
    vmcp_environments = relationship("VMCPEnvironment", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class MCPServer(Base):
    """
    MCP Server configuration model.

    Stores individual MCP servers that can be connected to and used.
    Each server has its own configuration, transport type, and authentication settings.
    """
    __tablename__ = "mcp_servers"

    # Primary identifier (composite of user_id and server_id)
    id = Column(String(255), primary_key=True, index=True)

    # User relationship (always the dummy user in OSS)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # MCP server identification
    server_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Configuration stored as JSON
    # Contains: transport_type, command/url, args, env, auth_config, etc.
    mcp_server_config = Column(JSONType, nullable=False)

    # OAuth state for MCP server authentication
    # Stores access tokens and refresh tokens for OAuth-enabled MCP servers
    oauth_state = Column(JSONType, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="mcp_servers")
    vmcp_mappings = relationship("VMCPMCPMapping", back_populates="mcp_server", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MCPServer(id='{self.id}', server_id='{self.server_id}', name='{self.name}')>"


class VMCP(Base):
    """
    Virtual MCP (vMCP) configuration model.

    A vMCP aggregates multiple MCP servers into a single unified interface.
    It provides a consolidated view of tools, resources, and prompts from multiple servers.
    """
    __tablename__ = "vmcps"

    # Primary identifier (composite of user_id and vmcp_id)
    id = Column(String(255), primary_key=True, index=True)

    # User relationship (always the dummy user in OSS)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # vMCP identification
    vmcp_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Configuration stored as JSON
    # Contains: list of mcp_server_ids, tool mappings, resource mappings, etc.
    vmcp_config = Column(JSONType, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="vmcps")
    mcp_mappings = relationship("VMCPMCPMapping", back_populates="vmcp", cascade="all, delete-orphan")
    environments = relationship("VMCPEnvironment", back_populates="vmcp", cascade="all, delete-orphan")
    stats = relationship("VMCPStats", back_populates="vmcp", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<VMCP(id='{self.id}', vmcp_id='{self.vmcp_id}', name='{self.name}')>"


class VMCPMCPMapping(Base):
    """
    Mapping between VMCPs and MCP Servers.

    Defines which MCP servers are included in each vMCP and their configuration.
    """
    __tablename__ = "vmcp_mcp_mappings"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    vmcp_id = Column(String(255), ForeignKey("vmcps.id"), nullable=False, index=True)
    mcp_server_id = Column(String(255), ForeignKey("mcp_servers.id"), nullable=False, index=True)

    # Mapping configuration (tool filters, resource filters, etc.)
    mapping_config = Column(JSONType, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    vmcp = relationship("VMCP", back_populates="mcp_mappings")
    mcp_server = relationship("MCPServer", back_populates="vmcp_mappings")

    # Unique constraint
    __table_args__ = (
        Index('idx_vmcp_mcp_unique', 'vmcp_id', 'mcp_server_id', unique=True),
    )

    def __repr__(self):
        return f"<VMCPMCPMapping(vmcp_id='{self.vmcp_id}', mcp_server_id='{self.mcp_server_id}')>"


class VMCPEnvironment(Base):
    """
    Environment variables for VMCPs.

    Stores environment variables that are injected when executing tools
    from MCP servers within a vMCP.
    """
    __tablename__ = "vmcp_environments"

    id = Column(String(255), primary_key=True, index=True)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vmcp_id = Column(String(255), ForeignKey("vmcps.id"), nullable=False, index=True)

    # Environment variables as JSON
    environment_vars = Column(JSONType, nullable=False, default={})

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="vmcp_environments")
    vmcp = relationship("VMCP", back_populates="environments")

    def __repr__(self):
        return f"<VMCPEnvironment(vmcp_id='{self.vmcp_id}')>"


class VMCPStats(Base):
    """
    Usage statistics for VMCPs.

    Tracks tool calls, resource reads, prompt usage, and errors for analytics.
    """
    __tablename__ = "vmcp_stats"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key
    vmcp_id = Column(String(255), ForeignKey("vmcps.id"), nullable=False, index=True)

    # Operation details
    operation_type = Column(String(50), nullable=False, index=True)  # tool_call, resource_read, prompt_get
    operation_name = Column(String(255), nullable=False)  # Name of tool/resource/prompt
    mcp_server_id = Column(String(255), nullable=True, index=True)  # Which MCP server was used

    # Success/failure
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)

    # Timing
    duration_ms = Column(Integer, nullable=True)  # Operation duration in milliseconds

    # Additional metadata
    operation_metadata = Column(JSONType, nullable=True)  # Additional operation metadata

    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    vmcp = relationship("VMCP", back_populates="stats")

    # Indexes for querying
    __table_args__ = (
        Index('idx_stats_vmcp_created', 'vmcp_id', 'created_at'),
        Index('idx_stats_operation_type', 'vmcp_id', 'operation_type'),
    )

    def __repr__(self):
        return f"<VMCPStats(vmcp_id='{self.vmcp_id}', operation='{self.operation_type}:{self.operation_name}', success={self.success})>"


class ThirdPartyOAuthState(Base):
    """
    OAuth state for third-party MCP server authentication.

    Stores OAuth state data during the OAuth flow for MCP servers
    that require OAuth authentication.
    """
    __tablename__ = "third_party_oauth_states"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(255), unique=True, nullable=False, index=True)
    state_data = Column(JSONType, nullable=False)

    # Expiration
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<ThirdPartyOAuthState(state='{self.state}')>"


class OAuthStateMapping(Base):
    """
    OAuth State Mapping model for MCP OAuth flows.
    
    Manages OAuth state mappings for MCP server authentication, supporting:
    - User and server associations
    - PKCE code challenge and verifier storage
    - OAuth flow state management
    - State expiration and cleanup
    - Secure state validation
    """
    __tablename__ = "oauth_state_mapping"

    # Primary identifier
    id = Column(Integer, primary_key=True, index=True)

    # MCP state token (unique, used for lookups)
    mcp_state = Column(String(255), unique=True, nullable=False, index=True)

    # User and server information
    user_id = Column(String(50), nullable=False, index=True)
    server_name = Column(String(255), nullable=False, index=True)

    # OAuth state parameter
    state = Column(Text, nullable=False, index=True)

    # PKCE parameters
    code_challenge = Column(String(255), nullable=True)
    code_verifier = Column(String(255), nullable=True)

    # OAuth endpoints
    token_url = Column(Text, nullable=True)
    callback_url = Column(Text, nullable=True)

    # OAuth client information
    client_id = Column(Text, nullable=True)
    client_secret = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<OAuthStateMapping(id={self.id}, mcp_state='{self.mcp_state[:8]}...', user_id='{self.user_id}', server_name='{self.server_name}')>"

    @property
    def is_expired(self):
        """Check if the OAuth state has expired"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        # Ensure both datetimes are timezone-aware for comparison
        if self.expires_at.tzinfo is None:
            # If expires_at is naive, assume it's UTC
            expires_at_aware = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at_aware = self.expires_at
        return now > expires_at_aware

    @property
    def is_valid(self):
        """Check if OAuth state is valid (not expired)"""
        return not self.is_expired

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            'id': self.id,
            'mcp_state': self.mcp_state,
            'user_id': self.user_id,
            'server_name': self.server_name,
            'state': self.state,
            'code_challenge': self.code_challenge,
            'code_verifier': self.code_verifier,
            'token_url': self.token_url,
            'callback_url': self.callback_url,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'created_at': self.created_at.timestamp() if self.created_at else None,
            'expires_at': self.expires_at.timestamp() if self.expires_at else None
        }


class ApplicationLog(Base):
    """
    Application logs for debugging and monitoring.

    Stores important application events, errors, and debug information.
    """
    __tablename__ = "application_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Log details
    level = Column(String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name = Column(String(255), nullable=False, index=True)
    message = Column(Text, nullable=False)

    # Context
    vmcp_id = Column(String(255), nullable=True, index=True)
    mcp_server_id = Column(String(255), nullable=True, index=True)

    # Additional data
    log_metadata = Column(JSONType, nullable=True)
    traceback = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index('idx_logs_level_created', 'level', 'created_at'),
        Index('idx_logs_vmcp_created', 'vmcp_id', 'created_at'),
    )

    def __repr__(self):
        return f"<ApplicationLog(level='{self.level}', logger='{self.logger_name}', message='{self.message[:50]}...')>"


class GlobalMCPServerRegistry(Base):
    """
    Global MCP Server Registry model

    Stores all global MCP server configurations that are available to all users.
    This is the central registry for discoverable and installable MCP servers.

    Attributes:
        server_id: Primary key, unique identifier for the MCP server (string)
        name: Display name of the MCP server
        description: Description of the MCP server functionality
        mcp_registry_config: JSONB field containing MCPRegistryConfig data
        mcp_server_registry_config: JSONB field containing MCPRegistryConfig data (duplicate for compatibility)
        mcp_server_config: JSONB field containing MCPServerConfig data
        server_metadata: JSONB field containing additional metadata (category, icon, etc.)
        stats: JSONB field containing usage statistics
        created_at: When this server was added to the global registry
        updated_at: Last update timestamp
    """

    __tablename__ = "global_mcp_server_registry"

    # Primary identifier
    server_id = Column(String(255), primary_key=True, index=True)

    # Basic server information
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # MCP configuration data
    mcp_registry_config = Column(JSONType, nullable=False, default={})
    mcp_server_registry_config = Column(JSONType, nullable=False, default={})
    mcp_server_config = Column(JSONType, nullable=False, default={})

    # Additional data
    server_metadata = Column(JSONType, nullable=False, default={})
    stats = Column(JSONType, nullable=False, default={})

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<GlobalMCPServerRegistry(server_id='{self.server_id}', name='{self.name}')>"

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            'server_id': self.server_id,
            'name': self.name,
            'description': self.description,
            'mcp_registry_config': self.mcp_registry_config,
            'mcp_server_registry_config': self.mcp_server_registry_config,
            'mcp_server_config': self.mcp_server_config,
            'server_metadata': self.server_metadata,
            'stats': self.stats,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class GlobalPublicVMCPRegistry(Base):
    """
    Global Public vMCP Registry model
    
    Stores all publicly shared vMCP configurations that are available to all users.
    This is the central registry for discoverable and installable public vMCPs.
    
    Attributes:
        public_vmcp_id: Primary key, unique identifier for the public vMCP (string)
        type: Type/category of the vMCP
        vmcp_registry_config: JSON field containing VMCPRegistryConfig data
        vmcp_config: JSON field containing VMCPConfig data
        created_at: When this vMCP was added to the global registry
        updated_at: Last update timestamp
    """
    
    __tablename__ = "global_public_vmcp_registry"
    
    # Primary identifier
    public_vmcp_id = Column(String(255), primary_key=True, index=True)
    
    # Type/category
    type = Column(String(255), nullable=True, index=True)
    
    # vMCP configuration data (stored as JSON in PostgreSQL JSONB, TEXT in SQLite)
    # JSONType automatically handles parsing for both database types
    vmcp_registry_config = Column(JSONType, nullable=False, default={})
    vmcp_config = Column(JSONType, nullable=False, default={})
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<GlobalPublicVMCPRegistry(public_vmcp_id='{self.public_vmcp_id}', type='{self.type}')>"
    
    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            'public_vmcp_id': self.public_vmcp_id,
            'type': self.type,
            'vmcp_registry_config': self.vmcp_registry_config,
            'vmcp_config': self.vmcp_config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# ========================== BLOB STORAGE MODEL ==========================

class Blob(Base):
    """
    Blob storage for general file resources.
    
    This model handles:
    - General file resources (when vmcp_id is set)
    - Binary data storage using BLOB for SQLite
    - File metadata and organization
    - User-specific blob access control
    """
    __tablename__ = "blobs"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Widget association (optional, kept for backward compatibility but no foreign key)
    widget_id = Column(String, nullable=True, index=True)
    
    # Resource association (optional)
    vmcp_id = Column(String, nullable=True, index=True)  # Associated vMCP
    
    # File information
    original_filename = Column(String(500), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String, nullable=True)  # Relative path within resource
    resource_name = Column(String(500), nullable=True)  # Resource name for vMCPs
    
    # File content - using BLOB for SQLite binary storage
    content = Column(Text, nullable=False)  # File content (base64 encoded for binary files)
    content_type = Column(String(255), nullable=False)  # MIME type
    size = Column(Integer, nullable=False)  # File size in bytes
    checksum = Column(String)  # MD5 checksum
    
    # Access control
    is_public = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_blob_widget', 'widget_id'),
        Index('idx_blob_user', 'user_id'),
        Index('idx_blob_vmcp', 'vmcp_id'),
    )

    def __repr__(self):
        if self.widget_id:
            return f"<Blob(id='{self.id}', file_path='{self.file_path}', widget_id='{self.widget_id}')>"
        else:
            return f"<Blob(id='{self.id}', filename='{self.original_filename}', vmcp_id='{self.vmcp_id}')>"
    
    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            'id': self.id,
            'original_filename': self.original_filename,
            'filename': self.filename,
            'file_path': self.file_path,
            'resource_name': self.resource_name,
            'content_type': self.content_type,
            'size': self.size,
            'vmcp_id': self.vmcp_id,
            'widget_id': self.widget_id,
            'is_public': self.is_public,
            'user_id': str(self.user_id),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def is_text_file(self):
        """Check if this is a text-based file"""
        text_types = [
            'text/', 'application/json', 'application/xml', 'application/csv',
            'application/javascript', 'application/typescript',
            'application/x-python', 'application/x-yaml', 'application/x-toml'
        ]
        return any(self.content_type.startswith(t) for t in text_types)
    
    @property
    def is_image_file(self):
        """Check if this is an image file"""
        return self.content_type.startswith('image/')
    
    @property
    def is_audio_file(self):
        """Check if this is an audio file"""
        return self.content_type.startswith('audio/')
    
    @property
    def is_video_file(self):
        """Check if this is a video file"""
        return self.content_type.startswith('video/')
    
    @property
    def is_document_file(self):
        """Check if this is a document file"""
        doc_types = [
            'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ]
        return self.content_type in doc_types
    
    @property
    def is_archive_file(self):
        """Check if this is an archive file"""
        archive_types = [
            'application/zip', 'application/x-tar', 'application/x-rar-compressed',
            'application/gzip', 'application/x-7z-compressed'
        ]
        return self.content_type in archive_types
    
    def get_file_extension(self):
        """Get file extension from original filename"""
        if '.' in self.original_filename:
            return '.' + self.original_filename.rsplit('.', 1)[1].lower()
        return ''
    
    def get_display_name(self):
        """Get display name for the file"""
        return self.original_filename or self.filename or f"blob_{self.id}"


# ========================== AGENT MANAGEMENT MODELS ==========================

class SessionMapping(Base):
    """
    Maps MCP session ID to agent name.
    
    Used in OSS mode where dummy tokens are generated, so we can't rely on
    bearer token to agent mapping. Instead, we use mcp-session-id from headers.
    """
    __tablename__ = "session_mappings"
    
    session_id = Column(String(255), primary_key=True, index=True)
    agent_name = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<SessionMapping(session_id='{self.session_id}', agent_name='{self.agent_name}')>"


class AgentInfo(Base):
    """
    Stores agent information per user.
    """
    __tablename__ = "agent_info"
    
    id = Column(String(255), primary_key=True, index=True)  # Composite: user_id + agent_name
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_name = Column(String(255), nullable=False, index=True)
    agent_info = Column(JSONType, nullable=False, default={})
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_agent_info_user_agent', 'user_id', 'agent_name'),
    )
    
    def __repr__(self):
        return f"<AgentInfo(user_id={self.user_id}, agent_name='{self.agent_name}')>"


class AgentTokens(Base):
    """
    Stores bearer tokens associated with agents per user.
    """
    __tablename__ = "agent_tokens"
    
    id = Column(String(255), primary_key=True, index=True)  # Composite: user_id + agent_name + token_hash
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_name = Column(String(255), nullable=False, index=True)
    bearer_token = Column(Text, nullable=False)  # Store full token
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_agent_tokens_user_agent', 'user_id', 'agent_name'),
    )
    
    def __repr__(self):
        return f"<AgentTokens(user_id={self.user_id}, agent_name='{self.agent_name}')>"


class AgentLogs(Base):
    """
    Stores agent logs per user.
    """
    __tablename__ = "agent_logs"
    
    id = Column(String(255), primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_name = Column(String(255), nullable=False, index=True)
    log_entry = Column(JSONType, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_agent_logs_user_agent', 'user_id', 'agent_name'),
        Index('idx_agent_logs_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AgentLogs(user_id={self.user_id}, agent_name='{self.agent_name}')>"


# Blob model handles both widget files and general file resources
