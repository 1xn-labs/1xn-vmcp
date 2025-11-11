#!/usr/bin/env python3
"""
Complete Everything MCP Server - Comprehensive demonstration of all MCP features
Showcases: Tools, Resources, Prompts, Sampling, Elicitation, Notifications,
           Authentication, Completions, Logging, Real-time data, Webhooks
"""

import asyncio
import contextlib
import json
import random
import shutil
import sqlite3
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import (
    Completion,
    CompletionArgument,
    CompletionContext,
    PromptReference,
    ResourceTemplateReference,
    SamplingMessage,
    TextContent,
)
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount

try:
    from .all_feature_server import mcp as all_feature_mcp  # type: ignore[import-untyped]
except ImportError:
    from all_feature_server import mcp as all_feature_mcp

import contextlib

from starlette.applications import Starlette
from starlette.routing import Mount
# ============================================================================
# ENUMS AND DATA MODELS
# ============================================================================

class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: Status
    priority: Priority
    created_at: datetime
    updated_at: datetime
    due_date: Optional[datetime] = None
    assignee: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class User:
    id: str
    username: str
    email: str
    full_name: str
    role: str
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorReading:
    id: str
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    location: str
    timestamp: datetime
    quality: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Notification:
    id: str
    type: str
    title: str
    message: str
    priority: Priority
    timestamp: datetime
    read: bool = False
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# AUTHENTICATION
# ============================================================================

class EverythingTokenVerifier(TokenVerifier):
    """Comprehensive token verifier with multiple auth methods."""

    def __init__(self):
        self.valid_tokens = {
            "admin_token_123": {
                "user_id": "admin",
                "username": "admin",
                "role": "administrator",
                "scopes": ["read", "write", "admin", "delete"],
                "expires_at": datetime.now() + timedelta(hours=24)
            },
            "user_token_456": {
                "user_id": "user1",
                "username": "john_doe",
                "role": "user",
                "scopes": ["read", "write"],
                "expires_at": datetime.now() + timedelta(hours=12)
            },
            "readonly_token_789": {
                "user_id": "readonly",
                "username": "readonly_user",
                "role": "viewer",
                "scopes": ["read"],
                "expires_at": datetime.now() + timedelta(hours=8)
            }
        }

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify the provided token and return access information."""
        if token in self.valid_tokens:
            token_data = self.valid_tokens[token]

            # Check if token is expired
            if datetime.now() > token_data["expires_at"]:
                return None

            # AccessToken constructor - using type: ignore since exact signature may vary
            # This code is not actively used as token_verifier is commented out in server setup
            return AccessToken(  # type: ignore[call-arg]
                token=token,
                scopes=token_data["scopes"],
                client_id=token_data.get("user_id", "unknown")  # Use user_id as client_id fallback
            )
        return None


# ============================================================================
# SYSTEM STATE MANAGEMENT
# ============================================================================

@dataclass
class EverythingSystem:
    """Comprehensive system state management."""

    # Core data stores
    tasks: Dict[str, Task] = field(default_factory=dict)
    users: Dict[str, User] = field(default_factory=dict)
    sensor_readings: List[SensorReading] = field(default_factory=list)
    notifications: Dict[str, Notification] = field(default_factory=dict)

    # System metrics
    system_metrics: Dict[str, Any] = field(default_factory=dict)
    performance_data: List[Dict[str, Any]] = field(default_factory=list)

    # File system
    temp_dir: Path = field(default_factory=lambda: Path(tempfile.mkdtemp()))

    # Database
    db_path: Optional[str] = None
    db_connection: Optional[sqlite3.Connection] = None

    # Real-time data
    live_data_enabled: bool = True
    webhook_endpoints: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize the system with sample data."""
        self._initialize_database()
        self._create_sample_data()
        self._setup_file_system()

    def _initialize_database(self):
        """Set up SQLite database with tables."""
        self.db_path = str(self.temp_dir / "everything.db")
        self.db_connection = sqlite3.connect(self.db_path, check_same_thread=False)

        cursor = self.db_connection.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_id TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                component TEXT,
                user_id TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                id TEXT PRIMARY KEY,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                tags TEXT
            )
        """)

        self.db_connection.commit()

    def _create_sample_data(self):
        """Create comprehensive sample data."""

        # Sample users
        sample_users = [
            User("user1", "john_doe", "john@example.com", "John Doe", "developer"),
            User("user2", "jane_smith", "jane@example.com", "Jane Smith", "manager"),
            User("user3", "bob_wilson", "bob@example.com", "Bob Wilson", "analyst"),
            User("admin", "admin_user", "admin@example.com", "Administrator", "admin")
        ]

        for user in sample_users:
            self.users[user.id] = user

        # Sample tasks
        sample_tasks = [
            Task(
                id=str(uuid.uuid4()),
                title="Implement new API endpoint",
                description="Create REST API for user management",
                status=Status.ACTIVE,
                priority=Priority.HIGH,
                created_at=datetime.now() - timedelta(days=2),
                updated_at=datetime.now() - timedelta(hours=3),
                assignee="user1",
                tags=["api", "backend", "development"],
                progress=0.6
            ),
            Task(
                id=str(uuid.uuid4()),
                title="Update documentation",
                description="Refresh API documentation with latest changes",
                status=Status.PENDING,
                priority=Priority.MEDIUM,
                created_at=datetime.now() - timedelta(days=1),
                updated_at=datetime.now() - timedelta(hours=8),
                assignee="user2",
                tags=["documentation", "maintenance"],
                progress=0.2
            ),
            Task(
                id=str(uuid.uuid4()),
                title="Security audit",
                description="Perform comprehensive security review",
                status=Status.COMPLETED,
                priority=Priority.CRITICAL,
                created_at=datetime.now() - timedelta(days=5),
                updated_at=datetime.now() - timedelta(days=1),
                assignee="admin",
                tags=["security", "audit", "compliance"],
                progress=1.0
            )
        ]

        for task in sample_tasks:
            self.tasks[task.id] = task

        # Initialize system metrics
        self.system_metrics = {
            "uptime_seconds": 3600,
            "memory_usage_mb": 256.7,
            "cpu_usage_percent": 23.4,
            "disk_usage_percent": 45.8,
            "active_connections": 12,
            "requests_per_minute": 150,
            "error_rate_percent": 0.8,
            "last_updated": datetime.now().isoformat()
        }

    def _setup_file_system(self):
        """Create sample file system structure."""

        # Create directories
        dirs = ["documents", "images", "data", "logs", "temp", "config"]
        for dir_name in dirs:
            (self.temp_dir / dir_name).mkdir(exist_ok=True)

        # Create sample files
        sample_files = {
            "documents/readme.md": "# Everything MCP Server\n\nComprehensive demonstration of all MCP features.",
            "documents/api_docs.json": json.dumps({
                "version": "1.0",
                "endpoints": ["/health", "/users", "/tasks"],
                "authentication": "Bearer token"
            }, indent=2),
            "config/settings.json": json.dumps({
                "debug": True,
                "log_level": "INFO",
                "features": ["auth", "notifications", "real_time"]
            }, indent=2),
            "data/sample.csv": "id,name,value\n1,test,100\n2,demo,200\n3,sample,300",
            "logs/access.log": f"{datetime.now().isoformat()} - INFO - Server started\n"
        }

        for file_path, content in sample_files.items():
            full_path = self.temp_dir / file_path
            full_path.write_text(content)


# ============================================================================
# BACKGROUND TASKS AND REAL-TIME SIMULATION
# ============================================================================

async def simulate_real_time_data(system: EverythingSystem):
    """Simulate real-time sensor data and system metrics."""

    sensor_types = ["temperature", "humidity", "pressure", "light", "motion"]
    locations = ["office", "warehouse", "server_room", "lobby", "parking"]

    while True:
        if system.live_data_enabled:
            try:
                # Generate sensor readings
                for _ in range(random.randint(1, 3)):
                    sensor_type = random.choice(sensor_types)
                    location = random.choice(locations)

                    # Generate realistic values based on sensor type
                    if sensor_type == "temperature":
                        value = 20 + random.gauss(0, 3)
                        unit = "°C"
                    elif sensor_type == "humidity":
                        value = max(0, min(100, 50 + random.gauss(0, 10)))
                        unit = "%"
                    elif sensor_type == "pressure":
                        value = 1013.25 + random.gauss(0, 20)
                        unit = "hPa"
                    elif sensor_type == "light":
                        base_value = 300 if 6 <= datetime.now().hour <= 18 else 50
                        value = max(0, base_value + random.gauss(0, 100))
                        unit = "lux"
                    else:  # motion
                        value = 1 if random.random() < 0.1 else 0
                        unit = "boolean"

                    reading = SensorReading(
                        id=str(uuid.uuid4()),
                        sensor_id=f"{sensor_type}_{location}",
                        sensor_type=sensor_type,
                        value=round(value, 2),
                        unit=unit,
                        location=location,
                        timestamp=datetime.now(),
                        quality=random.uniform(0.9, 1.0)
                    )

                    system.sensor_readings.append(reading)

                # Keep only last 1000 readings
                if len(system.sensor_readings) > 1000:
                    system.sensor_readings = system.sensor_readings[-1000:]

                # Update system metrics
                system.system_metrics.update({
                    "memory_usage_mb": 200 + random.gauss(0, 50),
                    "cpu_usage_percent": max(0, min(100, 25 + random.gauss(0, 15))),
                    "active_connections": max(0, 12 + random.randint(-3, 8)),
                    "requests_per_minute": max(0, 150 + random.randint(-30, 50)),
                    "error_rate_percent": max(0, 0.8 + random.gauss(0, 0.5)),
                    "uptime_seconds": system.system_metrics.get("uptime_seconds", 0) + 30,
                    "last_updated": datetime.now().isoformat()
                })

                # Record performance data point
                system.performance_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "response_time_ms": random.uniform(50, 300),
                    "throughput_rps": random.uniform(80, 200),
                    "error_count": random.randint(0, 5)
                })

                # Keep only last 100 performance points
                if len(system.performance_data) > 100:
                    system.performance_data = system.performance_data[-100:]

            except Exception:
                pass

        await asyncio.sleep(30)  # Update every 30 seconds


async def generate_notifications(system: EverythingSystem):
    """Generate system notifications and alerts."""

    notification_types = ["info", "warning", "error", "success"]

    while True:
        try:
            # Generate occasional notifications
            if random.random() < 0.3:  # 30% chance every cycle
                notification = Notification(
                    id=str(uuid.uuid4()),
                    type=random.choice(notification_types),
                    title=f"System Alert - {datetime.now().strftime('%H:%M')}",
                    message=f"Automated system notification generated at {datetime.now().isoformat()}",
                    priority=random.choice(list(Priority)),
                    timestamp=datetime.now(),
                    user_id=random.choice(list(system.users.keys())) if system.users else None
                )

                system.notifications[notification.id] = notification

                # Keep only last 50 notifications
                if len(system.notifications) > 50:
                    oldest_notifications = sorted(
                        system.notifications.items(),
                        key=lambda x: x[1].timestamp
                    )
                    for old_id, _ in oldest_notifications[:-50]:
                        del system.notifications[old_id]

            await asyncio.sleep(120)  # Check every 2 minutes

        except Exception:
            await asyncio.sleep(120)


async def cleanup_system(system: EverythingSystem):
    """Periodic system cleanup and maintenance."""

    while True:
        try:
            # Clean up old sensor readings
            cutoff_time = datetime.now() - timedelta(hours=24)
            system.sensor_readings = [
                reading for reading in system.sensor_readings
                if reading.timestamp > cutoff_time
            ]

            # Clean up old performance data
            system.performance_data = system.performance_data[-200:]

            # Update task progress randomly for active tasks
            for task in system.tasks.values():
                if task.status == Status.ACTIVE and random.random() < 0.1:
                    task.progress = min(1.0, task.progress + random.uniform(0.05, 0.15))
                    task.updated_at = datetime.now()

                    if task.progress >= 1.0:
                        task.status = Status.COMPLETED

            await asyncio.sleep(3600)  # Run every hour

        except Exception:
            await asyncio.sleep(3600)


# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[EverythingSystem]:
    """Manage comprehensive application lifecycle."""

    system = EverythingSystem()

    # Start all background tasks
    tasks = [
        asyncio.create_task(simulate_real_time_data(system)),
        asyncio.create_task(generate_notifications(system)),
        asyncio.create_task(cleanup_system(system))
    ]

    try:
        yield system
    finally:
        # Cleanup on shutdown
        for task in tasks:
            task.cancel()

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass

        # Close database connection
        if system.db_connection:
            system.db_connection.close()

        # Clean up temporary directory
        if system.temp_dir.exists():
            shutil.rmtree(system.temp_dir)


# ============================================================================
# MCP SERVER SETUP
# ============================================================================

# Create MCP server with comprehensive configuration
# mcp = FastMCP(
#     "Everything MCP Server",
#     lifespan=app_lifespan,
#     token_verifier=EverythingTokenVerifier(),
#     auth=AuthSettings(
#         issuer_url=AnyHttpUrl("https://auth.everything-server.com"),
#         resource_server_url=AnyHttpUrl("http://localhost:8000"),
#         required_scopes=["read"],
#     ),
# )

# Create MCP server with comprehensive configuration
# everything_mcp = FastMCP(
#     "Everything MCP Server",
#     lifespan=app_lifespan,
# )

mcp = FastMCP(
    "Everything MCP Server",
     stateless_http=True
)



# ============================================================================
# RESOURCES - Comprehensive data access
# ============================================================================

@mcp.resource("everything://dashboard")
def get_dashboard() -> str:
    """Get comprehensive system dashboard data."""

    dashboard_data = {
        "overview": {
            "total_users": 4,
            "active_tasks": 2,
            "completed_tasks": 1,
            "notifications": 12,
            "system_health": "good",
            "uptime": "6 hours 23 minutes"
        },
        "metrics": {
            "cpu_usage": 23.4,
            "memory_usage": 256.7,
            "disk_usage": 45.8,
            "network_requests": 150,
            "error_rate": 0.8
        },
        "recent_activity": [
            {"time": "10 minutes ago", "event": "New task created", "user": "john_doe"},
            {"time": "23 minutes ago", "event": "API endpoint called", "endpoint": "Weather API"},
            {"time": "1 hour ago", "event": "User logged in", "user": "jane_smith"}
        ],
        "alerts": [
            {"level": "warning", "message": "High CPU usage detected", "time": "5 minutes ago"},
            {"level": "info", "message": "Backup completed successfully", "time": "2 hours ago"}
        ],
        "generated_at": datetime.now().isoformat()
    }

    return json.dumps(dashboard_data, indent=2)


@mcp.resource("everything://users/{user_id}")
def get_user_profile(user_id: str) -> str:
    """Get detailed user profile information."""

    sample_user = {
        "id": user_id,
        "username": "sample_user",
        "email": "user@example.com",
        "full_name": "Sample User",
        "role": "developer",
        "active": True,
        "created_at": "2024-01-15T10:30:00Z",
        "last_login": "2024-08-05T14:22:33Z",
        "preferences": {
            "theme": "dark",
            "notifications": True,
            "timezone": "UTC",
            "language": "en"
        },
        "statistics": {
            "tasks_created": 15,
            "tasks_completed": 12,
            "api_calls_made": 234,
            "login_count": 89,
            "average_session_duration": "2.5 hours"
        },
        "permissions": [
            "read_tasks",
            "write_tasks",
            "read_users",
            "call_apis"
        ],
        "recent_activity": [
            {"action": "created_task", "timestamp": "2024-08-05T13:45:00Z", "details": "Implement new feature"},
            {"action": "updated_profile", "timestamp": "2024-08-05T09:15:00Z", "details": "Changed theme preference"},
            {"action": "logged_in", "timestamp": "2024-08-05T08:30:00Z", "details": "Web interface login"}
        ]
    }

    return json.dumps(sample_user, indent=2)


@mcp.resource("everything://tasks/{task_id}")
def get_task_details(task_id: str) -> str:
    """Get comprehensive task information."""

    sample_task = {
        "id": task_id,
        "title": "Implement Everything MCP Server",
        "description": "Create a comprehensive MCP server demonstrating all protocol features including tools, resources, prompts, sampling, and real-time capabilities.",
        "status": "active",
        "priority": "high",
        "progress": 0.75,
        "created_at": "2024-08-01T09:00:00Z",
        "updated_at": "2024-08-05T14:30:00Z",
        "due_date": "2024-08-10T17:00:00Z",
        "assignee": {
            "id": "user1",
            "username": "john_doe",
            "full_name": "John Doe"
        },
        "tags": ["mcp", "python", "server", "development"],
        "subtasks": [
            {"id": "st1", "title": "Set up project structure", "completed": True},
            {"id": "st2", "title": "Implement core MCP features", "completed": True},
            {"id": "st3", "title": "Add authentication", "completed": True},
            {"id": "st4", "title": "Create comprehensive examples", "completed": False},
            {"id": "st5", "title": "Write documentation", "completed": False}
        ],
        "time_tracking": {
            "estimated_hours": 40,
            "logged_hours": 28.5,
            "remaining_hours": 11.5
        },
        "comments": [
            {
                "id": "c1",
                "author": "jane_smith",
                "text": "Great progress on the core implementation!",
                "timestamp": "2024-08-04T16:20:00Z"
            }
        ],
        "attachments": [
            {"name": "design_doc.pdf", "size": "2.3 MB", "uploaded": "2024-08-02T11:15:00Z"}
        ]
    }

    return json.dumps(sample_task, indent=2)


@mcp.resource("everything://sensors/realtime")
def get_realtime_sensors() -> str:
    """Get current real-time sensor data."""

    # Generate sample real-time sensor data
    sensors = []
    sensor_types = ["temperature", "humidity", "pressure", "light", "motion"]
    locations = ["office", "warehouse", "server_room", "lobby"]

    for i, sensor_type in enumerate(sensor_types):
        for j, location in enumerate(locations):
            if sensor_type == "temperature":
                value = 20 + random.gauss(0, 3)
                unit = "°C"
                status = "normal" if 18 <= value <= 25 else "warning"
            elif sensor_type == "humidity":
                value = max(0, min(100, 50 + random.gauss(0, 10)))
                unit = "%"
                status = "normal" if 30 <= value <= 70 else "warning"
            elif sensor_type == "pressure":
                value = 1013.25 + random.gauss(0, 10)
                unit = "hPa"
                status = "normal"
            elif sensor_type == "light":
                hour = datetime.now().hour
                base_value = 300 if 6 <= hour <= 18 else 50
                value = max(0, base_value + random.gauss(0, 50))
                unit = "lux"
                status = "normal"
            else:  # motion
                value = 1 if random.random() < 0.1 else 0
                unit = "boolean"
                status = "active" if value else "inactive"

            sensors.append({
                "id": f"{sensor_type}_{location}_{i}{j}",
                "type": sensor_type,
                "location": location,
                "value": round(value, 2),
                "unit": unit,
                "status": status,
                "last_update": datetime.now().isoformat(),
                "quality": round(random.uniform(0.9, 1.0), 3)
            })

    result = {
        "sensors": sensors,
        "total_sensors": len(sensors),
        "active_sensors": len([s for s in sensors if s["status"] != "inactive"]),
        "last_updated": datetime.now().isoformat(),
        "update_frequency": "30 seconds"
    }

    return json.dumps(result, indent=2)


@mcp.resource("everything://files/{path}")
def get_file_content(path: str) -> str:
    """Get file system content with metadata."""

    sample_file = {
        "path": path,
        "name": path.split("/")[-1] if "/" in path else path,
        "type": "file",
        "size": 1024,
        "content": f"Sample content for file: {path}\n\nThis demonstrates file system resource access through the MCP protocol.",
        "metadata": {
            "created": "2024-08-01T10:00:00Z",
            "modified": "2024-08-05T14:30:00Z",
            "permissions": "rw-r--r--",
            "owner": "system",
            "mime_type": "text/plain",
            "encoding": "utf-8"
        },
        "checksums": {
            "md5": "d41d8cd98f00b204e9800998ecf8427e",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
    }

    return json.dumps(sample_file, indent=2)


@mcp.resource("everything://analytics/{metric}")
def get_analytics_data(metric: str) -> str:
    """Get analytics and performance metrics."""

    # Generate sample analytics based on metric type
    if metric == "performance":
        data_points = []
        base_time = datetime.now() - timedelta(hours=24)

        for i in range(48):  # 48 data points over 24 hours
            timestamp = base_time + timedelta(minutes=30 * i)
            data_points.append({
                "timestamp": timestamp.isoformat(),
                "response_time_ms": random.uniform(50, 300),
                "throughput_rps": random.uniform(80, 200),
                "error_rate": random.uniform(0, 5),
                "cpu_usage": random.uniform(10, 80),
                "memory_usage": random.uniform(200, 500)
            })

        analytics: Dict[str, Any] = {
            "metric": metric,
            "time_range": "24 hours",
            "data_points": data_points,
            "summary": {
                "avg_response_time": 175.3,
                "avg_throughput": 142.7,
                "total_requests": 205440,
                "error_count": 1647,
                "uptime_percentage": 99.2
            }
        }
    else:
        analytics = {
            "metric": metric,
            "value": random.uniform(10, 100),
            "unit": "percent",
            "trend": "increasing",
            "last_updated": datetime.now().isoformat(),
            "historical_data": [
                {"date": "2024-08-01", "value": 85.2},
                {"date": "2024-08-02", "value": 87.1},
                {"date": "2024-08-03", "value": 89.5},
                {"date": "2024-08-04", "value": 91.8},
                {"date": "2024-08-05", "value": 94.3}
            ]
        }

    return json.dumps(analytics, indent=2)


# ============================================================================
# TOOLS - Comprehensive functionality
# ============================================================================

@mcp.tool()
async def create_task(
    title: str,
    description: str,
    priority: Literal["low", "medium", "high", "critical"] = "medium",
    assignee: Optional[str] = None,
    due_date: Optional[str] = None,
    tags: Optional[List[str]] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Create a new task in the system.

    Args:
        title: Task title
        description: Detailed task description
        priority: Task priority level
        assignee: User ID to assign the task to
        due_date: Due date in ISO format
        tags: List of tags for categorization
    """
    await ctx.info(f"Creating new task: {title}")

    try:
        system = ctx.request_context.lifespan_context

        # Validate assignee exists
        if assignee and assignee not in system.users:
            return {"error": f"User {assignee} not found"}

        # Parse due date
        parsed_due_date = None
        if due_date:
            try:
                parsed_due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except ValueError:
                return {"error": "Invalid due date format. Use ISO format."}

        # Create task
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            title=title,
            description=description,
            status=Status.PENDING,
            priority=Priority(priority),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            due_date=parsed_due_date,
            assignee=assignee,
            tags=tags or []
        )

        system.tasks[task_id] = task

        # Log the event
        if system.db_connection:
            cursor = system.db_connection.cursor()
            cursor.execute(
                "INSERT INTO events (id, type, data, timestamp, user_id) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "task_created", json.dumps({"task_id": task_id, "title": title}),
                 datetime.now().isoformat(), assignee)
            )
            system.db_connection.commit()

        # Send notification
        await ctx.session.send_resource_list_changed()

        return {
            "success": True,
            "task_id": task_id,
            "title": title,
            "status": task.status.value,
            "priority": task.priority.value,
            "created_at": task.created_at.isoformat(),
            "assignee": assignee
        }

    except Exception as e:
        await ctx.error(f"Error creating task: {e}")
        return {"error": str(e)}


@mcp.tool()
async def update_task_status(
    task_id: str,
    status: Literal["active", "inactive", "pending", "completed", "failed"],
    progress: Optional[float] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Update task status and progress.

    Args:
        task_id: ID of the task to update
        status: New task status
        progress: Task progress (0.0 to 1.0)
    """
    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.debug(f"Updating task {task_id} status to {status}")

    try:
        system = ctx.request_context.lifespan_context

        if task_id not in system.tasks:
            return {"error": "Task not found"}

        task = system.tasks[task_id]
        old_status = task.status.value

        task.status = Status(status)
        task.updated_at = datetime.now()

        if progress is not None:
            if not 0.0 <= progress <= 1.0:
                return {"error": "Progress must be between 0.0 and 1.0"}
            task.progress = progress

        # Auto-complete task if progress is 100%
        if task.progress >= 1.0 and task.status != Status.COMPLETED:
            task.status = Status.COMPLETED

        await ctx.session.send_resource_list_changed()

        return {
            "success": True,
            "task_id": task_id,
            "old_status": old_status,
            "new_status": task.status.value,
            "progress": task.progress,
            "updated_at": task.updated_at.isoformat()
        }

    except Exception as e:
        await ctx.error(f"Error updating task status: {e}")
        return {"error": str(e)}


@mcp.tool()
async def search_everything(
    query: str,
    resource_types: Optional[List[str]] = None,
    limit: int = 20,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Comprehensive search across all system resources.

    Args:
        query: Search query string
        resource_types: Types of resources to search (tasks, users, sensors, notifications)
        limit: Maximum number of results to return
    """
    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info(f"Searching for: '{query}'")

    try:
        system = ctx.request_context.lifespan_context
        results = []

        query_lower = query.lower()
        resource_types = resource_types or ["tasks", "users", "sensors", "notifications"]

        # Search tasks
        if "tasks" in resource_types:
            for task in system.tasks.values():
                if (query_lower in task.title.lower() or
                    query_lower in task.description.lower() or
                    any(query_lower in tag.lower() for tag in task.tags)):

                    results.append({
                        "type": "task",
                        "id": task.id,
                        "title": task.title,
                        "description": task.description[:100] + "...",
                        "status": task.status.value,
                        "priority": task.priority.value,
                        "relevance_score": 0.9
                    })

        # Search users
        if "users" in resource_types:
            for user in system.users.values():
                if (query_lower in user.username.lower() or
                    query_lower in user.full_name.lower() or
                    query_lower in user.email.lower()):

                    results.append({
                        "type": "user",
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.full_name,
                        "role": user.role,
                        "active": user.active,
                        "relevance_score": 0.8
                    })

        # Search notifications
        if "notifications" in resource_types:
            for notification in system.notifications.values():
                if (query_lower in notification.title.lower() or
                    query_lower in notification.message.lower()):

                    results.append({
                        "type": "notification",
                        "id": notification.id,
                        "title": notification.title,
                        "message": notification.message[:100] + "...",
                        "priority": notification.priority.value,
                        "timestamp": notification.timestamp.isoformat(),
                        "relevance_score": 0.7
                    })

        # Search sensors
        if "sensors" in resource_types:
            for reading in system.sensor_readings[-50:]:  # Search recent readings
                if (query_lower in reading.sensor_type.lower() or
                    query_lower in reading.location.lower()):

                    results.append({
                        "type": "sensor",
                        "id": reading.id,
                        "sensor_id": reading.sensor_id,
                        "sensor_type": reading.sensor_type,
                        "location": reading.location,
                        "value": reading.value,
                        "unit": reading.unit,
                        "timestamp": reading.timestamp.isoformat(),
                        "relevance_score": 0.6
                    })

        # Sort by relevance and limit results
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:limit]

        return {
            "query": query,
            "total_results": len(results),
            "resource_types_searched": resource_types,
            "results": results,
            "search_time_ms": random.uniform(10, 50),  # Simulated search time
            "searched_at": datetime.now().isoformat()
        }

    except Exception as e:
        await ctx.error(f"Error searching: {e}")
        return {"error": str(e)}


@mcp.tool()
async def generate_report(
    report_type: Literal["summary", "detailed", "analytics", "security", "performance"],
    time_period: str = "7d",
    include_charts: bool = True,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Generate comprehensive system reports using AI assistance.

    Args:
        report_type: Type of report to generate
        time_period: Time period for the report (1d, 7d, 30d, 90d)
        include_charts: Whether to include chart data
    """
    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info(f"Generating {report_type} report for {time_period}")

    try:
        system = ctx.request_context.lifespan_context

        # Collect system data for report
        report_data = {
            "system_metrics": system.system_metrics,
            "total_tasks": len(system.tasks),
            "completed_tasks": len([t for t in system.tasks.values() if t.status == Status.COMPLETED]),
            "active_users": len([u for u in system.users.values() if u.active]),
            "total_notifications": len(system.notifications),
            "sensor_readings": len(system.sensor_readings)
        }

        # Prepare data summary for AI analysis
        data_summary = f"""
        System Report Data ({time_period}):
        - Total tasks: {report_data['total_tasks']}
        - Completed tasks: {report_data['completed_tasks']}
        - Active users: {report_data['active_users']}
        - System uptime: {report_data['system_metrics'].get('uptime_seconds', 0)} seconds
        - Memory usage: {report_data['system_metrics'].get('memory_usage_mb', 0)} MB
        - CPU usage: {report_data['system_metrics'].get('cpu_usage_percent', 0)}%
        - Error rate: {report_data['system_metrics'].get('error_rate_percent', 0)}%
        - Active connections: {report_data['system_metrics'].get('active_connections', 0)}
        """

        # Generate AI-powered insights based on report type
        if report_type == "summary":
            prompt = f"Create an executive summary report based on this system data: {data_summary}"
        elif report_type == "detailed":
            prompt = f"Generate a detailed operational report with specific recommendations: {data_summary}"
        elif report_type == "analytics":
            prompt = f"Provide analytical insights and trends analysis: {data_summary}"
        elif report_type == "security":
            prompt = f"Focus on security aspects and potential vulnerabilities: {data_summary}"
        else:  # performance
            prompt = f"Analyze system performance and optimization opportunities: {data_summary}"

        # Use AI sampling for report generation
        result = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt),
                )
            ],
            max_tokens=600,
        )

        ai_analysis = result.content.text if result.content.type == "text" else "Report generation failed"

        # Generate chart data if requested
        chart_data = None
        if include_charts:
            chart_data = {
                "task_completion_trend": [
                    {"date": "2024-08-01", "completed": 5, "created": 8},
                    {"date": "2024-08-02", "completed": 7, "created": 6},
                    {"date": "2024-08-03", "completed": 4, "created": 9},
                    {"date": "2024-08-04", "completed": 8, "created": 5},
                    {"date": "2024-08-05", "completed": 6, "created": 7}
                ],
                "system_performance": [
                    {"time": "00:00", "cpu": 15, "memory": 200, "response_time": 120},
                    {"time": "06:00", "cpu": 25, "memory": 250, "response_time": 140},
                    {"time": "12:00", "cpu": 45, "memory": 300, "response_time": 180},
                    {"time": "18:00", "cpu": 35, "memory": 280, "response_time": 160},
                    {"time": "23:00", "cpu": 20, "memory": 220, "response_time": 130}
                ]
            }

        return {
            "report_type": report_type,
            "time_period": time_period,
            "generated_at": datetime.now().isoformat(),
            "data_summary": report_data,
            "ai_analysis": ai_analysis,
            "chart_data": chart_data,
            "recommendations": [
                "Monitor task completion rates for potential bottlenecks",
                "Optimize memory usage during peak hours",
                "Implement proactive monitoring for error rate trends",
                "Consider scaling resources based on user activity patterns"
            ],
            "key_metrics": {
                "overall_health_score": 85,
                "performance_grade": "B+",
                "security_status": "Good",
                "user_satisfaction": "High"
            }
        }

    except Exception as e:
        await ctx.error(f"Error generating report: {e}")
        return {"error": str(e)}


@mcp.tool()
async def manage_notifications(
    action: Literal["list", "mark_read", "mark_all_read", "delete", "create"],
    notification_id: Optional[str] = None,
    message: Optional[str] = None,
    priority: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Comprehensive notification management system.

    Args:
        action: Action to perform
        notification_id: Specific notification ID for targeted actions
        message: Message for creating new notifications
        priority: Priority level for new notifications
    """
    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.debug(f"Managing notifications: {action}")

    try:
        system = ctx.request_context.lifespan_context

        if action == "list":
            notifications = []
            for notif in system.notifications.values():
                notifications.append({
                    "id": notif.id,
                    "type": notif.type,
                    "title": notif.title,
                    "message": notif.message,
                    "priority": notif.priority.value,
                    "timestamp": notif.timestamp.isoformat(),
                    "read": notif.read,
                    "user_id": notif.user_id
                })

            notifications.sort(key=lambda x: x["timestamp"], reverse=True)

            return {
                "action": action,
                "notifications": notifications,
                "total_count": len(notifications),
                "unread_count": len([n for n in notifications if not n["read"]])
            }

        elif action == "mark_read":
            if not notification_id:
                return {"error": "Notification ID required"}

            if notification_id not in system.notifications:
                return {"error": "Notification not found"}

            system.notifications[notification_id].read = True

            return {
                "success": True,
                "action": action,
                "notification_id": notification_id,
                "marked_read_at": datetime.now().isoformat()
            }

        elif action == "mark_all_read":
            count = 0
            for notif in system.notifications.values():
                if not notif.read:
                    notif.read = True
                    count += 1

            return {
                "success": True,
                "action": action,
                "marked_read_count": count,
                "marked_at": datetime.now().isoformat()
            }

        elif action == "delete":
            if not notification_id:
                return {"error": "Notification ID required"}

            if notification_id not in system.notifications:
                return {"error": "Notification not found"}

            del system.notifications[notification_id]

            return {
                "success": True,
                "action": action,
                "notification_id": notification_id,
                "deleted_at": datetime.now().isoformat()
            }

        elif action == "create":
            if not message:
                return {"error": "Message required for creating notification"}

            notification_id = str(uuid.uuid4())
            notification = Notification(
                id=notification_id,
                type="info",
                title="Custom Notification",
                message=message,
                priority=Priority(priority) if priority else Priority.MEDIUM,
                timestamp=datetime.now()
            )

            system.notifications[notification_id] = notification

            await ctx.session.send_resource_list_changed()

            return {
                "success": True,
                "action": action,
                "notification_id": notification_id,
                "message": message,
                "priority": notification.priority.value,
                "created_at": notification.timestamp.isoformat()
            }

        else:
            return {"error": f"Unknown action: {action}"}

    except Exception as e:
        await ctx.error(f"Error managing notifications: {e}")
        return {"error": str(e)}


@mcp.tool()
async def analyze_system_health(
    include_predictions: bool = True,
    detailed_analysis: bool = False,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Comprehensive system health analysis with AI-powered insights.

    Args:
        include_predictions: Whether to include predictive analysis
        detailed_analysis: Whether to perform detailed component analysis
    """
    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info("Analyzing system health with AI assistance")

    try:
        system = ctx.request_context.lifespan_context

        # Collect comprehensive health metrics
        health_metrics = {
            "system_metrics": system.system_metrics,
            "task_metrics": {
                "total": len(system.tasks),
                "active": len([t for t in system.tasks.values() if t.status == Status.ACTIVE]),
                "completed": len([t for t in system.tasks.values() if t.status == Status.COMPLETED]),
                "overdue": len([t for t in system.tasks.values()
                             if t.due_date and t.due_date < datetime.now() and t.status != Status.COMPLETED])
            },
            "user_metrics": {
                "total": len(system.users),
                "active": len([u for u in system.users.values() if u.active]),
                "recent_logins": len([u for u in system.users.values()
                                   if u.last_login and u.last_login > datetime.now() - timedelta(days=7)])
            },
            "sensor_metrics": {
                "total_readings": len(system.sensor_readings),
                "recent_readings": len([r for r in system.sensor_readings
                                     if r.timestamp > datetime.now() - timedelta(hours=1)]),
                "avg_quality": sum(r.quality for r in system.sensor_readings[-100:]) / min(100, len(system.sensor_readings))
            }
        }

        # Calculate overall health score
        cpu_score = max(0, 100 - health_metrics["system_metrics"].get("cpu_usage_percent", 0))
        memory_score = max(0, 100 - (health_metrics["system_metrics"].get("memory_usage_mb", 0) / 10))
        error_score = max(0, 100 - (health_metrics["system_metrics"].get("error_rate_percent", 0) * 10))
        task_completion_rate = (health_metrics["task_metrics"]["completed"] /
                               max(1, health_metrics["task_metrics"]["total"]) * 100)

        overall_health_score = (cpu_score + memory_score + error_score + task_completion_rate) / 4

        # Prepare data for AI analysis
        analysis_prompt = f"""
        Analyze this system health data and provide insights:

        System Metrics:
        - CPU Usage: {health_metrics['system_metrics'].get('cpu_usage_percent', 0)}%
        - Memory Usage: {health_metrics['system_metrics'].get('memory_usage_mb', 0)} MB
        - Error Rate: {health_metrics['system_metrics'].get('error_rate_percent', 0)}%
        - Active Connections: {health_metrics['system_metrics'].get('active_connections', 0)}
        - Uptime: {health_metrics['system_metrics'].get('uptime_seconds', 0)} seconds

        Task Metrics:
        - Total Tasks: {health_metrics['task_metrics']['total']}
        - Active Tasks: {health_metrics['task_metrics']['active']}
        - Completed Tasks: {health_metrics['task_metrics']['completed']}
        - Overdue Tasks: {health_metrics['task_metrics']['overdue']}

        Overall Health Score: {overall_health_score:.1f}/100

        Please provide:
        1. Health assessment (excellent/good/fair/poor)
        2. Key concerns or issues
        3. Specific recommendations for improvement
        4. {'Predictive analysis for next 24-48 hours' if include_predictions else 'Current status summary'}
        """

        # Use AI sampling for health analysis
        result = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=analysis_prompt),
                )
            ],
            max_tokens=500,
        )

        ai_insights = result.content.text if result.content.type == "text" else "Health analysis unavailable"

        # Generate component-specific analysis if requested
        component_analysis = None
        if detailed_analysis:
            component_analysis = {
                "database": {"status": "healthy", "connections": 5, "query_time_avg": 25.3},
                "file_system": {"status": "healthy", "disk_usage": 45.8, "io_operations": 150},
                "network": {"status": "healthy", "latency_avg": 12.4, "packet_loss": 0.01},
                "authentication": {"status": "healthy", "active_sessions": 8, "failed_logins": 2},
                "real_time_data": {"status": "healthy", "update_frequency": 30, "data_quality": 0.95}
            }

        return {
            "overall_health_score": round(overall_health_score, 1),
            "health_grade": "A" if overall_health_score >= 90 else "B" if overall_health_score >= 80 else "C" if overall_health_score >= 70 else "D",
            "system_metrics": health_metrics,
            "ai_insights": ai_insights,
            "component_analysis": component_analysis,
            "recommendations": [
                "Monitor CPU usage during peak hours",
                "Implement automated task prioritization",
                "Set up proactive alerting for critical metrics",
                "Consider memory optimization for better performance"
            ],
            "alerts": [
                {"level": "info", "message": "System operating within normal parameters"},
                {"level": "warning", "message": f"{health_metrics['task_metrics']['overdue']} tasks are overdue"}
            ] if health_metrics['task_metrics']['overdue'] > 0 else [
                {"level": "info", "message": "All tasks are on schedule"}
            ],
            "analyzed_at": datetime.now().isoformat(),
            "next_analysis_recommended": (datetime.now() + timedelta(hours=6)).isoformat()
        }

    except Exception as e:
        await ctx.error(f"Error analyzing system health: {e}")
        return {"error": str(e)}


@mcp.tool()
async def simulate_webhook_event(
    event_type: str,
    payload: Dict[str, Any],
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """
    Simulate webhook events for testing and demonstration.

    Args:
        event_type: Type of webhook event
        payload: Event payload data
    """
    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info(f"Simulating webhook event: {event_type}")

    try:
        system = ctx.request_context.lifespan_context

        # Process different event types
        if event_type == "task.created":
            task_data = payload.get("task", {})
            await ctx.info(f"Webhook: New task created - {task_data.get('title', 'Unknown')}")

            # Create notification
            notification = Notification(
                id=str(uuid.uuid4()),
                type="info",
                title="New Task Created",
                message=f"Task '{task_data.get('title', 'Unknown')}' has been created via webhook",
                priority=Priority.MEDIUM,
                timestamp=datetime.now()
            )
            system.notifications[notification.id] = notification

        elif event_type == "system.alert":
            alert_data = payload.get("alert", {})
            await ctx.warning(f"Webhook: System alert - {alert_data.get('message', 'Unknown alert')}")

            # Create high-priority notification
            notification = Notification(
                id=str(uuid.uuid4()),
                type="warning",
                title="System Alert",
                message=alert_data.get("message", "System alert received via webhook"),
                priority=Priority.HIGH,
                timestamp=datetime.now()
            )
            system.notifications[notification.id] = notification

        elif event_type == "user.login":
            user_data = payload.get("user", {})
            user_id = user_data.get("id")

            if user_id and user_id in system.users:
                system.users[user_id].last_login = datetime.now()
                await ctx.debug(f"Webhook: User login recorded for {user_id}")

        # Send resource update notification
        await ctx.session.send_resource_list_changed()

        return {
            "success": True,
            "event_type": event_type,
            "processed_at": datetime.now().isoformat(),
            "payload_size": len(json.dumps(payload)),
            "notifications_created": 1 if event_type in ["task.created", "system.alert"] else 0
        }

    except Exception as e:
        await ctx.error(f"Error processing webhook event: {e}")
        return {"error": str(e)}


# ============================================================================
# PROMPTS - Comprehensive templates
# ============================================================================

@mcp.prompt()
def system_administration_prompt(
    task_type: str = "maintenance",
    urgency: Literal["low", "medium", "high", "critical"] = "medium",
    system_component: str = "general"
) -> str:
    """Generate comprehensive system administration prompts."""

    task_guidance = {
        "maintenance": "Routine system maintenance and optimization procedures",
        "troubleshooting": "Problem diagnosis and resolution strategies",
        "monitoring": "System monitoring and alerting configuration",
        "security": "Security hardening and vulnerability assessment",
        "backup": "Data backup and disaster recovery planning",
        "scaling": "System scaling and performance optimization"
    }

    urgency_context = {
        "low": "Planned maintenance window, non-critical operations",
        "medium": "Standard operational procedures, moderate priority",
        "high": "Urgent attention required, business impact possible",
        "critical": "Immediate action needed, system stability at risk"
    }

    return f"""
System Administration Task: {task_guidance.get(task_type, task_type)}
Component Focus: {system_component}
Urgency Level: {urgency_context.get(urgency, "standard priority")}

Please provide a comprehensive administration plan including:

1. Pre-Task Assessment
   - Current system status evaluation
   - Risk assessment and mitigation strategies
   - Required resources and permissions
   - Backup and rollback procedures

2. Execution Strategy
   - Step-by-step procedures
   - Safety checkpoints and validations
   - Progress monitoring methods
   - Communication protocols

3. Post-Task Verification
   - System functionality validation
   - Performance impact assessment
   - Documentation requirements
   - Stakeholder notification

4. Ongoing Monitoring
   - Key metrics to track
   - Alert thresholds and escalation
   - Follow-up maintenance schedule
   - Lessons learned documentation

Consider system dependencies, user impact, and regulatory compliance throughout the process.
"""


@mcp.prompt()
def data_analysis_prompt(
    analysis_type: str = "exploratory",
    data_sources: Optional[List[str]] = None,
    business_objectives: str = "insights"
) -> str:
    """Generate data analysis and reporting prompts."""

    data_sources = data_sources or ["database", "sensors", "logs", "apis"]

    analysis_types = {
        "exploratory": "Discover patterns and relationships in the data",
        "diagnostic": "Understand why certain events or trends occurred",
        "predictive": "Forecast future trends and outcomes",
        "prescriptive": "Recommend specific actions based on analysis",
        "descriptive": "Summarize and describe current data patterns"
    }

    return f"""
Data Analysis Project: {analysis_types.get(analysis_type, analysis_type)}
Data Sources: {', '.join(data_sources)}
Business Objectives: {business_objectives}

Design a comprehensive data analysis approach:

1. Data Discovery and Preparation
   - Data source identification and access
   - Data quality assessment and cleaning
   - Feature engineering and transformation
   - Statistical summary and profiling

2. Analysis Methodology
   - Appropriate analytical techniques
   - Statistical tests and validation methods
   - Visualization and presentation strategies
   - Model selection and validation
   - Bias detection and mitigation

3. Results Interpretation
   - Key findings and insights
   - Statistical significance assessment
   - Business impact quantification
   - Limitations and assumptions

4. Actionable Recommendations
   - Specific business recommendations
   - Implementation roadmap
   - Success metrics and KPIs
   - Risk assessment and mitigation

5. Communication and Reporting
   - Executive summary for stakeholders
   - Technical documentation
   - Interactive dashboards and visualizations
   - Follow-up and monitoring plan

Ensure all analysis is reproducible, well-documented, and aligned with business objectives.
"""


@mcp.prompt()
def incident_response_prompt(
    incident_type: str = "system_outage",
    severity: Literal["low", "medium", "high", "critical"] = "high",
    affected_systems: Optional[List[str]] = None
) -> str:
    """Generate incident response and crisis management prompts."""

    affected_systems = affected_systems or ["web_services", "database", "authentication"]

    incident_types = {
        "system_outage": "Complete or partial system unavailability",
        "security_breach": "Unauthorized access or data compromise",
        "data_loss": "Critical data corruption or deletion",
        "performance_degradation": "Significant system slowdown or poor response times",
        "integration_failure": "External service integration problems"
    }

    severity_levels = {
        "low": "Minimal impact, affects few users or non-critical functions",
        "medium": "Moderate impact, affects some users or important functions",
        "high": "Significant impact, affects many users or critical functions",
        "critical": "Severe impact, affects all users or business-critical functions"
    }

    return f"""
Incident Response Plan: {incident_types.get(incident_type, incident_type)}
Severity Level: {severity_levels.get(severity, "high impact")}
Affected Systems: {', '.join(affected_systems)}

Execute comprehensive incident response:

1. Immediate Response (0-15 minutes)
   - Incident confirmation and initial assessment
   - Stakeholder notification and escalation
   - Emergency response team activation
   - Communication channel establishment

2. Investigation and Containment (15-60 minutes)
   - Root cause analysis initiation
   - System isolation and containment
   - Impact assessment and user communication
   - Temporary workarounds and service degradation

3. Resolution and Recovery (1-4 hours)
   - Permanent fix implementation
   - System restoration and validation
   - Data integrity verification
   - Service monitoring and stabilization

4. Post-Incident Analysis (24-48 hours)
   - Comprehensive incident review
   - Root cause documentation
   - Process improvement recommendations
   - Stakeholder communication and lessons learned

5. Prevention and Preparedness
   - Proactive monitoring enhancements
   - Process and procedure updates
   - Team training and skill development
   - Incident response plan refinement

Maintain clear communication, document all actions, and prioritize user impact mitigation throughout the response.
"""


@mcp.prompt()
def project_management_prompt(
    project_scope: str = "software_development",
    team_size: int = 5,
    timeline_weeks: int = 12,
    complexity: Literal["simple", "moderate", "complex"] = "moderate"
) -> str:
    """Generate comprehensive project management prompts."""

    scope_types = {
        "software_development": "Custom software application development",
        "infrastructure_upgrade": "System infrastructure modernization",
        "data_migration": "Large-scale data transfer and transformation",
        "security_implementation": "Security framework and controls deployment",
        "process_optimization": "Business process improvement and automation"
    }

    complexity_factors = {
        "simple": "Well-defined requirements, familiar technology, minimal dependencies",
        "moderate": "Some requirement ambiguity, mixed technologies, moderate dependencies",
        "complex": "Evolving requirements, cutting-edge technology, extensive dependencies"
    }

    return f"""
Project Management Plan: {scope_types.get(project_scope, project_scope)}
Team Size: {team_size} members
Timeline: {timeline_weeks} weeks
Complexity: {complexity_factors.get(complexity, "standard complexity")}

Develop a comprehensive project management strategy:

1. Project Initiation and Planning
   - Stakeholder identification and engagement
   - Requirements gathering and documentation
   - Scope definition and change management
   - Risk assessment and mitigation planning
   - Resource allocation and team structure

2. Execution and Monitoring
   - Task breakdown and work package creation
   - Progress tracking and milestone management
   - Quality assurance and testing procedures
   - Communication and reporting protocols
   - Issue management and escalation procedures

3. Risk and Change Management
   - Risk identification and assessment
   - Contingency planning and response strategies
   - Change request evaluation and approval
   - Impact analysis and stakeholder communication
   - Lessons learned and process improvement

4. Quality and Delivery
   - Quality standards and acceptance criteria
   - Testing strategy and validation procedures
   - Deployment planning and rollback procedures
   - User training and documentation
   - Post-deployment support and maintenance

5. Project Closure and Evaluation
   - Deliverable validation and acceptance
   - Project documentation and knowledge transfer
   - Team performance evaluation and feedback
   - Success metrics and ROI assessment
   - Future recommendations and continuous improvement

Ensure alignment with organizational goals, maintain stakeholder engagement, and deliver value within constraints.
"""


# ============================================================================
# AI-POWERED CONTENT GENERATION TOOLS
# ============================================================================

@mcp.tool()
async def generate_system_documentation(
    component: str,
    detail_level: Literal["overview", "detailed", "technical"] = "detailed",
    ctx: Optional[Context] = None
) -> str:
    """Generate comprehensive system documentation using AI."""
    
    await ctx.info(f"Generating {detail_level} documentation for {component}")

    prompt = f"""
    Generate {detail_level} documentation for the {component} component of the Everything MCP Server.

    Include:
    - Component overview and purpose
    - Architecture and design principles
    - API endpoints and data models
    - Configuration and deployment
    - Troubleshooting and maintenance
    - Security considerations
    - Performance optimization
    - Integration patterns

    Make it comprehensive, well-structured, and suitable for both technical and non-technical audiences.
    """

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=800,
    )

    return result.content.text if result.content.type == "text" else "Documentation generation failed"


@mcp.tool()
async def create_user_stories(
    feature_area: str,
    user_personas: Optional[List[str]] = None,
    complexity: Literal["simple", "medium", "complex"] = "medium",
    ctx: Optional[Context] = None
) -> str:
    """Generate user stories for feature development."""

    user_personas = user_personas or ["end_user", "administrator", "developer"]

    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info(f"Creating user stories for {feature_area}")

    prompt = f"""
    Create comprehensive user stories for the {feature_area} feature area.

    User Personas: {', '.join(user_personas)}
    Complexity Level: {complexity}

    For each persona, create user stories that include:
    - User story format (As a... I want... So that...)
    - Acceptance criteria
    - Definition of done
    - Technical considerations
    - Testing scenarios
    - Success metrics

    Focus on value delivery and user experience while considering technical feasibility.
    """

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=600,
    )

    return result.content.text if result.content.type == "text" else "User story generation failed"


@mcp.tool()
async def generate_test_cases(
    component: str,
    test_type: Literal["unit", "integration", "e2e", "performance"] = "integration",
    coverage_level: Literal["basic", "comprehensive", "exhaustive"] = "comprehensive",
    ctx: Optional[Context] = None
) -> str:
    """Generate comprehensive test cases for system components."""
    
    await ctx.info(f"Generating {test_type} test cases for {component}")

    prompt = f"""
    Generate {coverage_level} {test_type} test cases for the {component} component.

    Include:
    - Test case identification and description
    - Preconditions and test data setup
    - Step-by-step test procedures
    - Expected results and validation criteria
    - Error scenarios and edge cases
    - Performance benchmarks (if applicable)
    - Test environment requirements
    - Automation considerations

    Ensure test cases are clear, repeatable, and cover both positive and negative scenarios.
    """

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=700,
    )

    return result.content.text if result.content.type == "text" else "Test case generation failed"


# ============================================================================
# ELICITATION - Interactive data gathering
# ============================================================================

class ProjectRequirements(BaseModel):
    """Schema for collecting project requirements."""

    functional_requirements: List[str] = Field(
        description="List of functional requirements for the project"
    )
    non_functional_requirements: List[str] = Field(
        description="List of non-functional requirements (performance, security, etc.)"
    )
    constraints: List[str] = Field(
        description="List of project constraints (budget, timeline, technology, etc.)"
    )
    assumptions: List[str] = Field(
        description="List of assumptions about the project"
    )
    risks: List[str] = Field(
        description="List of potential risks and mitigation strategies"
    )


@mcp.tool()
async def gather_requirements(
    project_type: str,
    stakeholder_roles: Optional[List[str]] = None,
    ctx: Optional[Context] = None
) -> str:
    """Interactive requirements gathering process."""

    stakeholder_roles = stakeholder_roles or ["end_user", "manager", "technical_lead"]

    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info(f"Starting requirements gathering for {project_type}")

    # Use elicitation to gather requirements interactively
    result = await ctx.elicit(
        message=f"Please provide requirements for the {project_type} project. Consider the stakeholder roles: {', '.join(stakeholder_roles)}",
        schema=ProjectRequirements,
    )

    if result.action == "accept" and hasattr(result, 'data') and result.data:
        requirements = result.data
        return f"[SUCCESS] Requirements gathered for {project_type}:\n" + \
               f"Functional: {len(requirements.functional_requirements)} items\n" + \
               f"Non-functional: {len(requirements.non_functional_requirements)} items\n" + \
               f"Constraints: {len(requirements.constraints)} items\n" + \
               f"Assumptions: {len(requirements.assumptions)} items\n" + \
               f"Risks: {len(requirements.risks)} items"
    elif result.action == "decline":
        return "[CANCELLED] Requirements gathering cancelled by user"
    else:
        return "[CANCELLED] Requirements gathering cancelled"


class UserResearchData(BaseModel):
    """Schema for collecting user research data."""

    user_personas: List[Dict[str, Any]] = Field(
        description="List of user personas with their characteristics"
    )
    pain_points: List[str] = Field(
        description="List of user pain points and frustrations"
    )
    feature_requests: List[str] = Field(
        description="List of requested features and improvements"
    )
    usability_insights: List[str] = Field(
        description="List of usability insights and observations"
    )


@mcp.tool()
async def conduct_user_research(
    research_type: str,
    target_audience: Optional[List[str]] = None,
    research_methods: Optional[List[str]] = None,
    ctx: Optional[Context] = None
) -> str:
    """Conduct comprehensive user research and analysis."""

    target_audience = target_audience or ["end_users", "power_users", "administrators"]
    research_methods = research_methods or ["surveys", "interviews", "usability_testing"]

    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info(f"Conducting {research_type} user research")

    # Use elicitation to gather user research data interactively
    result = await ctx.elicit(
        message=f"Please provide user research data for {research_type} research targeting {', '.join(target_audience)} using methods: {', '.join(research_methods)}",
        schema=UserResearchData,
    )

    if result.action == "accept" and hasattr(result, 'data') and result.data:
        research_data = result.data
        return f"[SUCCESS] User research completed for {research_type}:\n" + \
               f"Personas: {len(research_data.user_personas)} identified\n" + \
               f"Pain points: {len(research_data.pain_points)} documented\n" + \
               f"Feature requests: {len(research_data.feature_requests)} collected\n" + \
               f"Usability insights: {len(research_data.usability_insights)} gathered"
    elif result.action == "decline":
        return "[CANCELLED] User research cancelled by user"
    else:
        return "[CANCELLED] User research cancelled"


# ============================================================================
# NOTIFICATION TOOLS - Real-time system alerts
# ============================================================================

@mcp.tool()
async def send_system_health_alert(
    alert_type: str,
    severity: Literal["info", "warning", "error", "critical"],
    message: str,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Send system health alerts and notifications."""
    
    await ctx.warning(f"System alert: {alert_type} - {message}")

    # In a real implementation, this would send notifications to various channels
    # such as email, Slack, SMS, or dashboard alerts

    notification_data = {
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "system_component": "everything_server",
        "recommended_action": "Monitor system metrics and logs"
    }

    # Log the alert for tracking
    if ctx.request_context.lifespan_context.db_connection:
        cursor = ctx.request_context.lifespan_context.db_connection.cursor()
        cursor.execute(
            "INSERT INTO logs (level, message, timestamp, component) VALUES (?, ?, ?, ?)",
            (severity.upper(), message, datetime.now().isoformat(), "system_alert")
        )
        ctx.request_context.lifespan_context.db_connection.commit()

    return {
        "success": True,
        "notification_sent": True,
        "notification_data": notification_data,
        "sent_at": datetime.now().isoformat()
    }


@mcp.tool()
async def log_user_activity(
    user_id: str,
    activity_type: str,
    details: Dict[str, Any],
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Log user activity for analytics and notifications."""

    assert ctx is not None  # FastMCP guarantees ctx is provided
    await ctx.info(f"User activity: {user_id} - {activity_type}")

    notification_data = {
        "user_id": user_id,
        "activity_type": activity_type,
        "details": details,
        "timestamp": datetime.now().isoformat(),
        "session_id": str(uuid.uuid4())
    }

    # Log user activity for analytics
    if ctx.request_context.lifespan_context.db_connection:
        cursor = ctx.request_context.lifespan_context.db_connection.cursor()
        cursor.execute(
            "INSERT INTO events (id, type, data, timestamp, user_id) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), activity_type, json.dumps(details),
             datetime.now().isoformat(), user_id)
        )
        ctx.request_context.lifespan_context.db_connection.commit()

    return {
        "success": True,
        "activity_logged": True,
        "activity_data": notification_data,
        "logged_at": datetime.now().isoformat()
    }


# ============================================================================
# COMPLETIONS - Argument completion suggestions
# ============================================================================

@mcp.completion()
async def handle_completion(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,
    context: CompletionContext | None,
) -> Completion | None:
    """Provide completions for prompts and resources."""

    # Complete task priorities for the create_task tool
    if isinstance(ref, ResourceTemplateReference):
        if ref.uri == "everything://tasks/{task_id}" and argument.name == "task_id":
            # Return sample task IDs
            return Completion(
                values=["task-001", "task-002", "task-003"],
                hasMore=False,
            )

    # Complete user IDs for user profile resources
    if isinstance(ref, ResourceTemplateReference):
        if ref.uri == "everything://users/{user_id}" and argument.name == "user_id":
            return Completion(
                values=["user1", "user2", "user3", "admin"],
                hasMore=False,
            )

    # Complete priority levels for task creation
    if isinstance(ref, PromptReference):
        if ref.name == "system_administration_prompt" and argument.name == "urgency":
            return Completion(
                values=["low", "medium", "high", "critical"],
                hasMore=False,
            )

    return None


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

# if __name__ == "__main__":
#     print("🚀 Starting Everything MCP Server...")
#     print("📊 Comprehensive demonstration of all MCP protocol features")
#     print("🔧 Features: Tools, Resources, Prompts, Sampling, Elicitation, Notifications")
#     print("🔐 Authentication: Bearer token with role-based access")
#     print("📈 Real-time: Live sensor data and system metrics")
#     print("🤖 AI-powered: Content generation and analysis")
#     print("🌐 Webhooks: Event-driven integrations")
#     print("📝 Logging: Comprehensive audit trail")
#     print("=" * 60)

#     # Use the FastMCP run method instead of uvicorn directly
#     mcp.run(transport="streamable-http")

    # Create a combined lifespan to manage both session managers
@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(all_feature_mcp.session_manager.run())
        await stack.enter_async_context(mcp.session_manager.run())
        yield


# Create the Starlette app and mount the MCP servers
app = Starlette(
    routes=[
        Mount("/allfeature", all_feature_mcp.streamable_http_app()),
        Mount("/everything", mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)

# Add health check endpoint
@app.route("/health")
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "1xn_noauth_servers"})

# run the Starlette app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0", port=8000)

