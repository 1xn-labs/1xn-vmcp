# convert_to_postman.py
import json
import requests

def convert_openapi_to_postman(openapi_file, output_file):
    """Convert OpenAPI to Postman collection using Postman API"""
    
    # Read OpenAPI file
    with open(openapi_file, 'r') as f:
        openapi_data = json.load(f)
    
    # Use Postman's conversion API
    url = "https://api.getpostman.com/import/openapi"
    
    # Or convert manually (basic structure)
    postman_collection = {
        "info": {
            "name": openapi_data.get("info", {}).get("title", "API Collection"),
            "description": openapi_data.get("info", {}).get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": []
    }
    
    # Convert paths to Postman requests
    for path, methods in openapi_data.get("paths", {}).items():
        for method, details in methods.items():
            if method in ["get", "post", "put", "patch", "delete"]:
                request_item = {
                    "name": details.get("summary", path),
                    "request": {
                        "method": method.upper(),
                        "header": [],
                        "url": {
                            "raw": f"{{{{base_url}}}}{path}",
                            "host": ["{{base_url}}"],
                            "path": path.strip("/").split("/")
                        },
                        "description": details.get("description", "")
                    }
                }
                
                # Add request body if exists
                if "requestBody" in details:
                    request_item["request"]["body"] = {
                        "mode": "raw",
                        "raw": json.dumps(
                            details["requestBody"].get("content", {})
                            .get("application/json", {})
                            .get("example", {}),
                            indent=2
                        ),
                        "options": {
                            "raw": {
                                "language": "json"
                            }
                        }
                    }
                
                postman_collection["item"].append(request_item)
    
    # Add environment variable
    postman_collection["variable"] = [
        {
            "key": "base_url",
            "value": "http://localhost:8002",
            "type": "string"
        }
    ]
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(postman_collection, f, indent=2)
    
    print(f"✅ Postman collection saved to {output_file}")

if __name__ == "__main__":
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    openapi_file = os.path.join(script_dir, "openapi.json")
    output_file = os.path.join(script_dir, "postman_collection.json")
    
    convert_openapi_to_postman(openapi_file, output_file)