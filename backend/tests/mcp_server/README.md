# MCP Server

This package provides a combined MCP server that runs both the "Everything" and "All Feature" servers on the same endpoint.

## Features

- **Everything Server**: Comprehensive MCP server with all protocol features
- **All Feature Server**: Feature-rich MCP server with various tools and resources
- **Combined Endpoint**: Both servers accessible via different paths on the same port
- **Health Monitoring**: Built-in health check endpoint

## Endpoints

- `http://localhost:8001/everything` - Everything MCP Server
- `http://localhost:8001/allfeature` - All Feature MCP Server  
- `http://localhost:8001/health` - Health check endpoint
- `http://localhost:8001/` - Service information

## Installation

This package uses `uv` for dependency management:

```bash
# Install dependencies
uv sync

# Or install in development mode
uv sync --dev
```

## Usage

### Using uvx (recommended)

```bash
uvx vmcp start_mcp_servers
```

### Using uv run

```bash
uv run start_mcp_servers
```

### Direct execution

```bash
python start_mcp_servers.py
```

### Development mode

```bash
uv run dev
```

## Configuration

The server runs on:
- **Host**: 0.0.0.0 (all interfaces)
- **Port**: 8001
- **Log Level**: info

## Dependencies

- mcp>=1.0.0
- uvicorn>=0.24.0
- starlette>=0.27.0
- pydantic>=2.0.0
- fastapi>=0.100.0
- Pillow>=10.0.0
- pandas>=2.0.0
- aiohttp>=3.8.0
- pytz>=2023.3

## Development

To run in development mode with auto-reload:

```bash
uv run dev
```

## Testing

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_server
```

## Health Check

The server provides a health check endpoint at `/health` that returns:

```json
{
  "status": "healthy",
  "service": "mcp_servers",
  "endpoints": {
    "everything": "/everything",
    "allfeature": "/allfeature"
  },
  "port": 8001
}
```

