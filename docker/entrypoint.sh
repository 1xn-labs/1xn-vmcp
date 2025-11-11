#!/bin/bash
set -e

# Ensure PYTHONPATH is set
export PYTHONPATH=/app/src

echo "🚀 Starting vMCP OSS initialization..."

# Initialize database
echo "📊 Initializing database..."
python3 -c "
from vmcp.storage.database import init_db
from vmcp.storage.dummy_user import ensure_dummy_user
init_db()
ensure_dummy_user()
print('✓ Database initialized')
"

# Upload preconfigured MCP servers
echo "📦 Uploading preconfigured MCP servers..."
python3 -m vmcp.scripts.upload_preconfigured_servers || echo "⚠️ Warning: Could not upload preconfigured servers"

# Upload demo vMCPs
echo "🎨 Uploading demo vMCPs..."
python3 -m vmcp.scripts.upload_all_demo_vmcps || echo "⚠️ Warning: Could not upload demo vMCPs"

# Upload default VMCP (1xndemo)
echo "⭐ Uploading default VMCP (1xndemo)..."
python3 -m vmcp.scripts.upload_default_vmcp || echo "⚠️ Warning: Could not upload default VMCP"

echo "✅ Initialization complete!"
echo "🌐 Starting vMCP server..."

# Start the server
exec vmcp serve --host 0.0.0.0 --port 8000

