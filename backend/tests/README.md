# vMCP Backend Test Suite

Comprehensive test suite for the vMCP (Virtual MCP) backend, covering all major features including vMCP creation, MCP server integration, custom prompts, and custom tools.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Test Suites](#test-suites)
- [Writing New Tests](#writing-new-tests)

## Overview

This test suite provides comprehensive coverage for:

1. **vMCP Creation** - Basic CRUD operations for vMCP instances
2. **MCP Server Integration** - Adding servers and verifying tools/resources/prompts
3. **Custom Prompts** - Prompts with variables, tool calls, and resources
4. **Custom Tools** - Prompt, Python, and HTTP tool types
5. **Import Collections** - Postman and OpenAPI import functionality

## Prerequisites

### Required Services

Before running tests, ensure all required services are running:

1. **vMCP Backend Server** (port 8000)
   ```bash
   cd oss/backend
   python -m uvicorn src.vmcp.main:app --reload --port 8000
   ```

2. **MCP Test Servers** (port 8001)
   ```bash
   cd oss/backend
   python -m mcp_server.start_mcp_servers
   ```
   This starts:
   - Everything MCP Server: `http://localhost:8001/everything/mcp`
   - AllFeature MCP Server: `http://localhost:8001/allfeature/mcp`

3. **Test HTTP Server** (port 8002)
   ```bash
   cd oss/backend
   python -m test_server.test_http_server
   ```

### Dependencies

Install test dependencies:

```bash
cd oss/backend
pip install -e ".[dev]"
# or
pip install pytest pytest-asyncio pytest-cov pytest-html pytest-mock
```

## Test Structure

```
tests/
├── README.md                          # This file
├── conftest.py                        # Pytest fixtures and helpers
├── run_tests.sh                       # Test runner script
├── test_01_vmcp_creation.py          # Suite 1: vMCP creation tests
├── test_02_mcp_server_integration.py # Suite 2: MCP server integration
├── test_03_custom_prompts.py         # Suite 3: Custom prompts
├── test_04_custom_tools_prompt.py    # Suite 4: Prompt-type tools
├── test_05_custom_tools_python.py    # Suite 5: Python tools
├── test_06_custom_tools_http.py      # Suite 6: HTTP tools
└── test_07_import_collection.py      # Suite 7: Collection import
```

## Running Tests

### Quick Start

Use the test runner script (recommended):

```bash
cd oss/backend/tests
chmod +x run_tests.sh
./run_tests.sh
```

The script will:
1. Check if all required servers are running
2. Run all tests with coverage
3. Generate HTML and XML coverage reports
4. Display results

### Using pytest directly

The test suite is configured via `pyproject.toml`, so you can run pytest directly:

```bash
cd oss/backend

# Run all tests
pytest

# Run specific test suite
pytest tests/test_01_vmcp_creation.py

# Run specific test
pytest tests/test_01_vmcp_creation.py::TestVMCPCreation::test_create_vmcp_basic

# Run with verbose output
pytest -vv

# Run only fast tests (exclude slow tests)
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run with specific markers
pytest -m custom_prompts
pytest -m python_tool
```

### Command-line Options

```bash
# Run tests with extra verbosity
./run_tests.sh -vv

# Run specific test file
./run_tests.sh tests/test_03_custom_prompts.py

# Run with custom pytest options
./run_tests.sh -k "test_create" --maxfail=1
```

## Test Coverage

### Coverage Reports

After running tests, coverage reports are generated in multiple formats:

1. **HTML Report** - Interactive browsable report
   ```bash
   open htmlcov/index.html
   ```

2. **Terminal Report** - Shows coverage in console with missing lines

3. **XML Report** - `coverage.xml` for CI/CD integration

4. **Test Results HTML** - `test_reports/results.html`
   ```bash
   open test_reports/results.html
   ```

### Coverage Configuration

Coverage is configured via `.coveragerc`:
- Source: `src/vmcp`
- Excludes: tests, migrations, CLI scripts
- Threshold: Aiming for >80% coverage

## Test Suites

### Suite 1: vMCP Creation (`test_01_vmcp_creation.py`)

Tests basic vMCP operations:
- ✅ Create basic vMCP
- ✅ Create vMCP with system prompt
- ✅ Retrieve vMCP details
- ✅ List all vMCPs
- ✅ Update vMCP description

**Markers**: `vmcp_creation`

### Suite 2: MCP Server Integration (`test_02_mcp_server_integration.py`)

Tests MCP server integration:
- ✅ Add Everything MCP server
- ✅ Add AllFeature MCP server
- ✅ Verify tools from MCP server
- ✅ Verify prompts from MCP server
- ✅ Verify resources from MCP server
- ✅ Call MCP tools
- ✅ Get MCP prompts

**Markers**: `mcp_server`

### Suite 3: Custom Prompts (`test_03_custom_prompts.py`)

Tests custom prompts with various features:
- ✅ Simple prompts without variables
- ✅ List and get custom prompts
- ✅ Prompts with @param variables
- ✅ Prompts with @config system variables
- ✅ Prompts with @tool calls
- ✅ Prompts with @prompt references
- ✅ Prompts with @resource references
- ✅ Complex prompts with all features combined

**Markers**: `custom_prompts`, `variables`, `tool_calls`, `resources`

### Suite 4: Custom Tools - Prompt Type (`test_04_custom_tools_prompt.py`)

Tests prompt-based tools:
- ✅ Simple prompt tools
- ✅ List prompt tools via MCP
- ✅ Call prompt tools
- ✅ Prompt tools with @param variables
- ✅ Prompt tools with @config variables
- ✅ Prompt tools with MCP tool calls
- ✅ Complex prompt tools with all features

**Markers**: `prompt_tool`, `custom_tools`

### Suite 5: Custom Tools - Python Type (`test_05_custom_tools_python.py`)

Tests Python-based tools:
- ✅ Simple Python tools
- ✅ Python tools with different types (int, str, float, list, dict)
- ✅ Python tools with default values
- ✅ Python tools with complex logic (Fibonacci)
- ✅ Python tool error handling

**Markers**: `python_tool`, `custom_tools`

### Suite 6: Custom Tools - HTTP Type (`test_06_custom_tools_http.py`)

Tests HTTP-based tools:
- ✅ HTTP GET requests
- ✅ API Key header authentication
- ✅ Bearer token authentication
- ✅ Basic authentication
- ✅ Query parameters
- ✅ @param variable substitution in URLs
- ✅ @config variable substitution
- ✅ POST requests with JSON body
- ✅ PATCH requests

**Markers**: `http_tool`, `custom_tools`

### Suite 7: Import Collection (`test_07_import_collection.py`)

Tests collection import functionality:
- ✅ Import Postman collection
- ✅ Import OpenAPI specification
- ✅ Call imported tools
- ✅ Collections with authentication
- ✅ Collections with path variables
- ✅ Collections with multiple endpoints
- ✅ List imported tools

**Markers**: `collection_tool`, `integration`

## Writing New Tests

### Test Structure

Follow the existing pattern:

```python
"""
Test Suite X: Feature Name
Description of what this suite tests
"""

import pytest
import requests
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.mark.your_marker
class TestYourFeature:
    """Test feature description"""

    def test_basic_feature(self, base_url, create_vmcp, helpers):
        """Test X.Y: Description"""
        vmcp = create_vmcp
        print(f"\n📦 Test X.Y - Description: {vmcp['id']}")

        # Test implementation

        print("✅ Test passed")

    @pytest.mark.asyncio
    async def test_async_feature(self, base_url, create_vmcp, helpers):
        """Test X.Z: Async description"""
        vmcp = create_vmcp
        print(f"\n📦 Test X.Z - Async test: {vmcp['id']}")

        # Connect via MCP
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Test MCP operations

                print("✅ Async test passed")
```

### Available Fixtures

From `conftest.py`:

- **base_url** - Base URL for API (`http://localhost:8000/`)
- **mcp_servers** - Dict with MCP server URLs
- **test_http_server** - Test HTTP server URL
- **vmcp_name** - Unique vMCP name for each test
- **create_vmcp** - Pre-created vMCP instance
- **mcp_client** - Connected MCP client session
- **helpers** - Helper functions:
  - `get_vmcp(vmcp_id)` - Get vMCP details
  - `update_vmcp(vmcp_id, data)` - Update vMCP
  - `add_server(vmcp_id, url, name)` - Add MCP server

### Test Markers

Use markers to categorize tests:

```python
@pytest.mark.vmcp_creation
@pytest.mark.slow
@pytest.mark.integration
def test_something():
    pass
```

Available markers:
- `vmcp_creation` - vMCP creation tests
- `mcp_server` - MCP server integration tests
- `custom_prompts` - Custom prompt tests
- `custom_tools` - Custom tool tests
- `prompt_tool` - Prompt-type tool tests
- `python_tool` - Python tool tests
- `http_tool` - HTTP tool tests
- `collection_tool` - Collection import tests
- `variables` - Variable substitution tests
- `tool_calls` - Tool call tests
- `resources` - Resource handling tests
- `integration` - Integration tests
- `slow` - Slow running tests

## Troubleshooting

### Common Issues

**1. Servers not running**
```
ERROR: Not all required servers are running!
```
**Solution**: Start all required servers (see Prerequisites)

**2. Import errors**
```
ModuleNotFoundError: No module named 'vmcp'
```
**Solution**: Install package in development mode:
```bash
pip install -e .
```

**3. Test failures due to previous test data**
```
AssertionError: Expected 1 tool, got 5
```
**Solution**: vMCP instances are unique per test. Check test isolation.

**4. Connection errors**
```
ClientConnectorError: Cannot connect to host localhost:8000
```
**Solution**: Verify backend server is running and accessible

### Debug Mode

Run tests with more verbose output:

```bash
pytest -vv --log-cli-level=DEBUG
```

Show print statements:

```bash
pytest -s
```

Stop on first failure:

```bash
pytest -x
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd oss/backend
          pip install -e ".[dev]"

      - name: Start servers
        run: |
          cd oss/backend
          python -m uvicorn src.vmcp.main:app &
          python -m mcp_server.start_mcp_servers &
          python -m test_server.test_http_server &
          sleep 10

      - name: Run tests
        run: |
          cd oss/backend/tests
          ./run_tests.sh

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./oss/backend/coverage.xml
```

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure tests pass locally
3. Maintain >80% coverage
4. Add appropriate markers
5. Update this README if adding new test suites

## Support

For issues or questions:
- GitHub Issues: https://github.com/vmcp/vmcp/issues
- Documentation: https://docs.vmcp.dev
