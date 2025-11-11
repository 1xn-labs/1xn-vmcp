"""
FIXED conftest.py - Solves "Tool calls require user context" error in GitHub Actions

The issue: The MCP connections aren't passing the Authorization header properly,
causing get_user_context_proxy_server() to return None, which triggers the error.

The solution: Properly patch streamablehttp_client as an async context manager.
"""
import sys
import uuid
import os
import pytest
import asyncio
from contextlib import asynccontextmanager


def get_test_dummy_token():
    """Get the test authentication token from environment"""
    token = os.getenv("VMCP_DUMMY_USER_TOKEN", "vmcp-test-dummy-token")
    return token


# Import MCP library components BEFORE patching
from mcp import ClientSession
from mcp.client import streamable_http

# Store original function before any imports might cache it
_original_streamablehttp_client = streamable_http.streamablehttp_client


@asynccontextmanager
async def patched_streamablehttp_client(url: str, headers=None, **kwargs):
    """
    Patched streamablehttp_client that ALWAYS adds Authorization header.
    
    This is critical because without it, get_user_context_proxy_server()
    returns None and raises "Tool calls require user context".
    """
    # Create headers dict if not provided
    hdrs = dict(headers) if headers else {}
    
    # ALWAYS add Authorization if missing
    if "Authorization" not in hdrs:
        token = get_test_dummy_token()
        hdrs["Authorization"] = f"Bearer {token}"
        print(f"🔑 [conftest] Added Authorization header for: {url}")
    else:
        print(f"🔑 [conftest] Authorization already present for: {url}")
    
    # Call original with patched headers
    async with _original_streamablehttp_client(url, headers=hdrs, **kwargs) as result:
        yield result


# Apply the patch at module level
streamable_http.streamablehttp_client = patched_streamablehttp_client

# Also patch in sys.modules to catch any cached imports
if 'mcp.client.streamable_http' in sys.modules:
    sys.modules['mcp.client.streamable_http'].streamablehttp_client = patched_streamablehttp_client

# Also patch in mcp.client module if it exists
try:
    from mcp.client import streamable_http as client_streamable
    client_streamable.streamablehttp_client = patched_streamablehttp_client
except ImportError:
    pass

# Export for convenience
streamablehttp_client = patched_streamablehttp_client


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def base_url():
    """Base URL for API requests"""
    return "http://localhost:8000/"


@pytest.fixture(scope="session")
def mcp_servers():
    """Test MCP servers"""
    return {
        "everything": "http://localhost:8001/everything/mcp",
        "allfeature": "http://localhost:8001/allfeature/mcp",
        "context7": "https://mcp.context7.com/mcp"
    }


@pytest.fixture(scope="session")
def test_http_server():
    """Test HTTP server URL"""
    return "http://localhost:8002"


@pytest.fixture(scope="session")
def auth_headers():
    """Authentication headers for API requests"""
    token = get_test_dummy_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def vmcp_name():
    """Generate unique vMCP name for each test"""
    uuid_string = str(uuid.uuid4())
    return f"test_vmcp_{uuid_string[0:12]}"


@pytest.fixture
async def create_vmcp(base_url, vmcp_name, auth_headers, request):
    """Create a vMCP with proper authentication"""
    import requests
    
    print(f"\n📦 [conftest] Creating vMCP: {vmcp_name}")
    response = requests.post(
        base_url + "api/vmcps/create",
        json={"name": vmcp_name, "description": "Test vMCP"},
        headers=auth_headers
    )
    
    if response.status_code != 200:
        print(f"❌ [conftest] Failed to create vMCP: {response.status_code}")
        print(f"   Response: {response.text}")
        
    assert response.status_code == 200, f"Failed to create vMCP: {response.text}"
    vmcp_data = response.json()["vMCP"]
    print(f"✅ [conftest] Created vMCP: {vmcp_data['id']}")

    def cleanup():
        delete_vmcp(base_url, vmcp_data["id"], auth_headers)

    request.addfinalizer(cleanup)
    return vmcp_data


@pytest.fixture
async def mcp_client(vmcp_name, base_url, auth_headers):
    """
    MCP client fixture - uses patched streamablehttp_client.
    
    The patch ensures Authorization header is ALWAYS included,
    which is required for get_user_context_proxy_server() to work.
    """
    # Import the patched version
    from mcp.client.streamable_http import streamablehttp_client

    mcp_url = f"{base_url}private/{vmcp_name}/vmcp"
    print(f"\n🔗 [conftest] Connecting to MCP: {mcp_url}")
    print(f"   Token: {auth_headers['Authorization'][:30]}...")
    
    # The patched client will automatically add auth headers
    async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print(f"✅ [conftest] MCP session initialized")
            yield session


# ============================================================================
# HELPER FUNCTIONS - All include auth_headers
# ============================================================================

def get_vmcp_details(base_url, vmcp_id, auth_headers):
    """Get vMCP details with authentication"""
    import requests
    response = requests.get(
        base_url + f"api/vmcps/{vmcp_id}",
        headers=auth_headers
    )
    assert response.status_code == 200, f"Failed to get vMCP: {response.text}"
    return response.json()


def update_vmcp(base_url, vmcp_id, vmcp_data, auth_headers):
    """Update vMCP with authentication"""
    import requests
    response = requests.put(
        base_url + f"api/vmcps/{vmcp_id}",
        json=vmcp_data,
        headers=auth_headers
    )
    assert response.status_code == 200, f"Failed to update vMCP: {response.text}"
    return response.json()


def add_mcp_server(base_url, vmcp_id, server_url, server_name, auth_headers, transport="http"):
    """Add MCP server to vMCP with authentication"""
    import requests
    print(f"   [conftest] Adding server: {server_name} ({server_url})")
    response = requests.post(
        base_url + f"api/vmcps/{vmcp_id}/add-server",
        json={"server_data": {
            "name": server_name,
            "url": server_url,
            "transport": transport,
            "description": f"Test {server_name} MCP Server"
        }},
        headers=auth_headers
    )
    
    if response.status_code != 200:
        print(f"   ❌ [conftest] Failed to add server: {response.status_code}")
        print(f"      Response: {response.text}")
    
    assert response.status_code == 200, f"Failed to add server: {response.text}"
    return response.json()


def save_environment_variables(base_url, vmcp_id, env_vars, auth_headers):
    """Save environment variables with authentication"""
    import requests
    response = requests.post(
        base_url + f"api/vmcps/{vmcp_id}/environment-variables/save",
        json={"environment_variables": env_vars},
        headers=auth_headers
    )
    assert response.status_code == 200, f"Failed to save env vars: {response.text}"
    return response.json()


def delete_vmcp(base_url, vmcp_id, auth_headers):
    """Delete vMCP with authentication"""
    import requests
    try:
        response = requests.delete(
            base_url + f"api/vmcps/{vmcp_id}",
            headers=auth_headers
        )
        if response.status_code == 200:
            print(f"🗑️  [conftest] Deleted test vMCP: {vmcp_id}")
        else:
            print(f"⚠️  [conftest] Failed to delete vMCP {vmcp_id}: {response.status_code}")
    except Exception as e:
        print(f"⚠️  [conftest] Failed to delete vMCP {vmcp_id}: {e}")


@pytest.fixture
def helpers(base_url, auth_headers):
    """Helper functions with authentication built-in"""
    def add_server_wrapper(vmcp_id, url, name, transport="http"):
        return add_mcp_server(base_url, vmcp_id, url, name, auth_headers, transport)

    return {
        "get_vmcp": lambda vmcp_id: get_vmcp_details(base_url, vmcp_id, auth_headers),
        "update_vmcp": lambda vmcp_id, data: update_vmcp(base_url, vmcp_id, data, auth_headers),
        "add_server": add_server_wrapper,
        "save_env_vars": lambda vmcp_id, env_vars: save_environment_variables(base_url, vmcp_id, env_vars, auth_headers),
        "delete_vmcp": lambda vmcp_id: delete_vmcp(base_url, vmcp_id, auth_headers)
    }


# ============================================================================
# TEST ENVIRONMENT HOOKS
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment and verify configuration"""
    print("\n" + "=" * 80)
    print("🧪 TEST ENVIRONMENT SETUP")
    print("=" * 80)
    print(f"VMCP_DUMMY_USER_TOKEN: {os.getenv('VMCP_DUMMY_USER_TOKEN', 'NOT SET')}")
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT SET')}")
    print(f"VMCP_DATABASE_URL: {os.getenv('VMCP_DATABASE_URL', 'NOT SET')}")
    print("=" * 80 + "\n")
    
    # Verify token is set
    token = get_test_dummy_token()
    assert token, "VMCP_DUMMY_USER_TOKEN must be set"
    print(f"✅ Test token verified: {token[:20]}...")
    
    yield
    
    print("\n" + "=" * 80)
    print("🧪 TEST ENVIRONMENT TEARDOWN")
    print("=" * 80 + "\n")


def pytest_runtest_makereport(item, call):
    """Hook to add extra logging on test failures"""
    if call.when == "call" and call.excinfo is not None:
        print(f"\n❌ [conftest] Test failed: {item.nodeid}")
        print(f"   Error: {call.excinfo.typename}: {call.excinfo.value}")
