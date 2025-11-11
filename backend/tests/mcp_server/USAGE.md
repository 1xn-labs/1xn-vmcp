# MCP Server Usage Guide

This document explains how to use the combined MCP server setup.

## Quick Start

### Option 1: Using uvx (Recommended)
```bash
uvx vmcp start_mcp_servers
```

### Option 2: Using uv run
```bash
uv run start_mcp_servers
```

### Option 3: Direct execution
```bash
cd /Users/apple/Projects/1mcpXagentsNapps/oss/backend/mcp_server
python start_mcp_servers.py
```

### Option 4: Using the shell script
```bash
cd /Users/apple/Projects/1mcpXagentsNapps/oss/backend/mcp_server
./start.sh
```

## Endpoints

Once started, the server will be available at:

- **Root**: http://localhost:8001/
- **Everything Server**: http://localhost:8001/everything
- **All Feature Server**: http://localhost:8001/allfeature
- **Health Check**: http://localhost:8001/health

## Testing

To test the endpoints, you can use the included test script:

```bash
cd /Users/apple/Projects/1mcpXagentsNapps/oss/backend/mcp_server
python test_endpoints.py
```

## MCP Client Connection

To connect with an MCP client, use these URLs:

```json
{
  "everything": "http://localhost:8001/everything",
  "allfeature": "http://localhost:8001/allfeature"
}
```

## Development

For development with auto-reload:

```bash
uv run dev
```

## Dependencies

The server requires these Python packages (automatically installed with uv):
- mcp>=1.0.0
- uvicorn>=0.24.0
- starlette>=0.27.0
- pydantic>=2.0.0
- fastapi>=0.100.0
- Pillow>=10.0.0
- pandas>=2.0.0
- aiohttp>=3.8.0
- pytz>=2023.3

## Troubleshooting

### Port already in use
If port 8001 is already in use, you can modify the port in `start_mcp_servers.py`:

```python
uvicorn.run(
    app,
    host="0.0.0.0",
    port=8002,  # Change this port
    log_level="info"
)
```

### Import errors
Make sure you're running from the correct directory:
```bash
cd /Users/apple/Projects/1mcpXagentsNapps/oss/backend/mcp_server
```

### Missing dependencies
Install dependencies with uv:
```bash
uv sync
```

## File Structure

```
mcp_server/
├── __init__.py
├── start_mcp_servers.py      # Main launcher
├── everything_server.py      # Everything MCP server
├── all_feature_server.py     # All Feature MCP server
├── worldcities.csv          # Data file for weather features
├── pyproject.toml           # uv configuration
├── README.md                # Documentation
├── USAGE.md                 # This file
├── test_endpoints.py        # Test script
└── start.sh                 # Shell startup script
```

