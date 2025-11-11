#!/bin/bash

# MCP Server Startup Script
# This script starts the combined MCP servers on localhost:8001

echo "🚀 Starting MCP Servers..."
echo "📊 Everything Server: http://localhost:8001/everything"
echo "🔧 All Feature Server: http://localhost:8001/allfeature"
echo "❤️  Health Check: http://localhost:8001/health"
echo "=" * 60

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using uv to start servers..."
    uv run python start_mcp_servers.py
else
    echo "Using python directly..."
    python start_mcp_servers.py
fi

