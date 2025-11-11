#!/usr/bin/env python3
"""
Generate OpenAPI schema for the test HTTP server
"""

import json
from test_http_server import app  # Import your FastAPI app

# Generate OpenAPI schema
openapi_schema = app.openapi()

# Save to file in the test_server directory
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(script_dir, "openapi.json")

with open(output_path, "w") as f:
    json.dump(openapi_schema, f, indent=2)

print(f"✅ OpenAPI JSON generated: {output_path}")