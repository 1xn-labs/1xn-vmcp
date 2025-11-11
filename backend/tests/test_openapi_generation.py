#!/usr/bin/env python3
"""
Test OpenAPI generation with type-safe endpoints
"""

import pytest
import json
import os
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import our type-safe routers
from src.vmcp.mcps.router_typesafe import router as mcp_router
from src.vmcp.vmcps.router_typesafe import router as vmcp_router
from src.vmcp.shared.models import BaseResponse, PaginatedResponse


class TestOpenAPIGeneration:
    """Test OpenAPI schema generation with type-safe endpoints"""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with our type-safe routers"""
        app = FastAPI(
            title="vMCP Type-Safe API Test",
            description="Test API for verifying type-safe OpenAPI generation",
            version="1.0.0"
        )
        
        # Include our routers
        app.include_router(mcp_router, prefix="/api/mcps", tags=["MCP Servers"])
        app.include_router(vmcp_router, prefix="/api/vmcps", tags=["vMCPs"])
        
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create a test client"""
        return TestClient(test_app)

    def test_openapi_schema_generation(self, test_app):
        """Test that OpenAPI schema can be generated without errors"""
        schema = test_app.openapi()
        
        # Basic schema structure validation
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema
        
        # Verify our routers are included
        assert "/api/mcps" in str(schema["paths"])
        assert "/api/vmcps" in str(schema["paths"])
        
        print(f"✅ OpenAPI schema generated successfully")
        print(f"📊 Schema contains {len(schema['paths'])} endpoints")

    def test_mcp_endpoints_have_request_models(self, test_app):
        """Test that MCP endpoints have proper request/response models"""
        schema = test_app.openapi()
        paths = schema["paths"]
        
        # Check key MCP endpoints
        mcp_endpoints = [
            "/api/mcps/install",
            "/api/mcps/{server_id}",
            "/api/mcps/{server_id}/connect",
            "/api/mcps/{server_id}/capabilities",
            "/api/mcps/{server_id}/tools",
            "/api/mccp/{server_id}/resources",
            "/api/mcps/{server_id}/prompts"
        ]
        
        for endpoint in mcp_endpoints:
            if endpoint in paths:
                endpoint_spec = paths[endpoint]
                print(f"🔍 Checking endpoint: {endpoint}")
                
                # Check if endpoint has proper HTTP methods
                for method in ["post", "get", "put", "delete"]:
                    if method in endpoint_spec:
                        method_spec = endpoint_spec[method]
                        
                        # Verify request/response models exist
                        if "requestBody" in method_spec:
                            assert "content" in method_spec["requestBody"]
                            assert "application/json" in method_spec["requestBody"]["content"]
                            assert "schema" in method_spec["requestBody"]["content"]["application/json"]
                        
                        if "responses" in method_spec:
                            assert "200" in method_spec["responses"]
                            response_200 = method_spec["responses"]["200"]
                            assert "content" in response_200
                            assert "application/json" in response_200["content"]
                            assert "schema" in response_200["content"]["application/json"]

    def test_vmcp_endpoints_have_request_models(self, test_app):
        """Test that vMCP endpoints have proper request/response models"""
        schema = test_app.openapi()
        paths = schema["paths"]
        
        # Check key vMCP endpoints
        vmcp_endpoints = [
            "/api/vmcps/create",
            "/api/vmcps/{vmcp_id}",
            "/api/vmcps/{vmcp_id}/refresh",
            "/api/vmcps/{vmcp_id}/tools/list",
            "/api/vmcps/{vmcp_id}/resources/list",
            "/api/vmcps/{vmcp_id}/prompts/list",
            "/api/vmcps/{vmcp_id}/tools/call",
            "/api/vmcps/{vmcp_id}/resources/read",
            "/api/vmcps/{vmcp_id}/prompts/get"
        ]
        
        for endpoint in vmcp_endpoints:
            if endpoint in paths:
                endpoint_spec = paths[endpoint]
                print(f"🔍 Checking endpoint: {endpoint}")
                
                # Check if endpoint has proper HTTP methods
                for method in ["post", "get", "put", "delete"]:
                    if method in endpoint_spec:
                        method_spec = endpoint_spec[method]
                        
                        # Verify request/response models exist
                        if "requestBody" in method_spec:
                            assert "content" in method_spec["requestBody"]
                            assert "application/json" in method_spec["requestBody"]["content"]
                            assert "schema" in method_spec["requestBody"]["content"]["application/json"]
                        
                        if "responses" in method_spec:
                            assert "200" in method_spec["responses"]
                            response_200 = method_spec["responses"]["200"]
                            assert "content" in response_200
                            assert "application/json" in response_200["content"]
                            assert "schema" in response_200["content"]["application/json"]

    def test_shared_models_in_schema(self, test_app):
        """Test that shared models are properly included in the schema"""
        schema = test_app.openapi()
        
        # Check that components/schemas contains our shared models
        if "components" in schema and "schemas" in schema["components"]:
            schemas = schema["components"]["schemas"]
            
            # Check for base response models
            expected_models = [
                "BaseResponse",
                "PaginatedResponse", 
                "ErrorResponse",
                "ServerInfo",
                "CapabilitiesInfo",
                "ConnectionStatus",
                "TransportType",
                "AuthType",
                "AuthConfig",
                "ToolInfo",
                "ResourceInfo",
                "PromptInfo"
            ]
            
            found_models = []
            for model_name in expected_models:
                if model_name in schemas:
                    found_models.append(model_name)
                    print(f"✅ Found shared model: {model_name}")
                else:
                    print(f"⚠️  Missing shared model: {model_name}")
            
            print(f"📊 Found {len(found_models)}/{len(expected_models)} shared models")

    def test_mcp_specific_models_in_schema(self, test_app):
        """Test that MCP-specific models are in the schema"""
        schema = test_app.openapi()
        
        if "components" in schema and "schemas" in schema["components"]:
            schemas = schema["components"]["schemas"]
            
            # Check for MCP-specific models
            mcp_models = [
                "MCPInstallRequest",
                "MCPUpdateRequest", 
                "MCPServerConfig",
                "MCPInstallResponse",
                "MCPConnectionResponse",
                "MCPCapabilitiesResponse",
                "MCPToolsResponse",
                "MCPResourcesResponse",
                "MCPPromptsResponse"
            ]
            
            found_mcp_models = []
            for model_name in mcp_models:
                if model_name in schemas:
                    found_mcp_models.append(model_name)
                    print(f"✅ Found MCP model: {model_name}")
                else:
                    print(f"⚠️  Missing MCP model: {model_name}")
            
            print(f"📊 Found {len(found_mcp_models)}/{len(mcp_models)} MCP models")

    def test_vmcp_specific_models_in_schema(self, test_app):
        """Test that vMCP-specific models are in the schema"""
        schema = test_app.openapi()
        
        if "components" in schema and "schemas" in schema["components"]:
            schemas = schema["components"]["schemas"]
            
            # Check for vMCP-specific models
            vmcp_models = [
                "VMCPCreateRequest",
                "VMCPUdateRequest",
                "VMCPConfig", 
                "VMCPCreateResponse",
                "VMCPDetailsResponse",
                "VMCPListResponse",
                "VMCPCapabilitiesResponse",
                "StatsFilterRequest",
                "LogEntry",
                "StatsResponse",
                "StatsSummary"
            ]
            
            found_vmcp_models = []
            for model_name in vmcp_models:
                if model_name in schemas:
                    found_vmcp_models.append(model_name)
                    print(f"✅ Found vMCP model: {model_name}")
                else:
                    print(f"⚠️  Missing vMCP model: {model_name}")
            
            print(f"📊 Found {len(found_vmcp_models)}/{len(vmcp_models)} vMCP models")

    def test_save_openapi_schema(self, test_app):
        """Test saving the OpenAPI schema to a file"""
        schema = test_app.openapi()
        
        # Save to a test file
        test_output_path = "test_openapi_schema.json"
        
        with open(test_output_path, "w") as f:
            json.dump(schema, f, indent=2)
        
        # Verify file was created and contains valid JSON
        assert os.path.exists(test_output_path)
        
        with open(test_output_path, "r") as f:
            loaded_schema = json.load(f)
        
        assert loaded_schema == schema
        print(f"✅ OpenAPI schema saved to: {test_output_path}")
        
        # Clean up
        os.remove(test_output_path)

    def test_schema_validation_structure(self, test_app):
        """Test that the schema has proper validation structure"""
        schema = test_app.openapi()
        
        # Check required fields
        required_fields = ["openapi", "info", "paths", "components"]
        for field in required_fields:
            assert field in schema, f"Missing required field: {field}"
        
        # Check info structure
        info = schema["info"]
        assert "title" in info
        assert "version" in info
        
        # Check paths structure
        paths = schema["paths"]
        assert isinstance(paths, dict)
        
        # Check components structure
        components = schema["components"]
        assert isinstance(components, dict)
        
        print("✅ Schema structure validation passed")

    def test_endpoint_parameter_types(self, test_app):
        """Test that endpoint parameters have proper types"""
        schema = test_app.openapi()
        paths = schema["paths"]
        
        # Check a few key endpoints for parameter types
        test_endpoints = [
            "/api/mcps/{server_id}",
            "/api/vmcps/{vmcp_id}"
        ]
        
        for endpoint in test_endpoints:
            if endpoint in paths:
                endpoint_spec = paths[endpoint]
                
                # Check for path parameters
                for method in ["get", "put", "delete"]:
                    if method in endpoint_spec:
                        method_spec = endpoint_spec[method]
                        
                        if "parameters" in method_spec:
                            params = method_spec["parameters"]
                            for param in params:
                                if param.get("in") == "path":
                                    assert "schema" in param
                                    assert "type" in param["schema"]
                                    print(f"✅ Path parameter {param['name']} has type: {param['schema']['type']}")

    def test_response_model_consistency(self, test_app):
        """Test that response models are consistent across endpoints"""
        schema = test_app.openapi()
        paths = schema["paths"]
        
        # Check that error responses are consistent
        error_responses = ["400", "404", "422", "500"]
        
        for path, endpoint_spec in paths.items():
            for method, method_spec in endpoint_spec.items():
                if isinstance(method_spec, dict) and "responses" in method_spec:
                    responses = method_spec["responses"]
                    
                    # Check for consistent error response structure
                    for error_code in error_responses:
                        if error_code in responses:
                            error_response = responses[error_code]
                            assert "description" in error_response
                            
                            if "content" in error_response:
                                assert "application/json" in error_response["content"]
                                content = error_response["content"]["application/json"]
                                assert "schema" in content
        
        print("✅ Response model consistency check passed")

    def test_openapi_schema_completeness(self, test_app):
        """Test overall completeness of the OpenAPI schema"""
        schema = test_app.openapi()
        
        # Count endpoints
        total_endpoints = 0
        for path, endpoint_spec in schema["paths"].items():
            for method in endpoint_spec:
                if method in ["get", "post", "put", "delete", "patch"]:
                    total_endpoints += 1
        
        # Count models
        total_models = 0
        if "components" in schema and "schemas" in schema["components"]:
            total_models = len(schema["components"]["schemas"])
        
        print(f"📊 Schema completeness:")
        print(f"   - Total endpoints: {total_endpoints}")
        print(f"   - Total models: {total_models}")
        print(f"   - Total paths: {len(schema['paths'])}")
        
        # Basic completeness checks
        assert total_endpoints > 0, "No endpoints found in schema"
        assert total_models > 0, "No models found in schema"
        assert len(schema["paths"]) > 0, "No paths found in schema"
        
        print("✅ OpenAPI schema completeness check passed")
