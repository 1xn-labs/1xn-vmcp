#!/usr/bin/env python3
"""
Test model compatibility between old and new routers

NOTE: This test is skipped because the old routers have been removed.
This test was used during the migration period to ensure compatibility.
"""

import pytest
import json
from typing import Dict, Any
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Skip all tests in this module since old routers no longer exist
pytestmark = pytest.mark.skip(reason="Old routers have been removed - test no longer applicable")

# Import new routers only (old routers no longer exist)
from src.vmcp.mcps.router_typesafe import router as new_mcp_router
from src.vmcp.vmcps.router_typesafe import router as new_vmcp_router


class TestModelCompatibility:
    """Test that old and new routers have compatible models"""

    @pytest.fixture
    def old_app(self):
        """Create app with old routers"""
        app = FastAPI(title="Old Router Test")
        app.include_router(old_mcp_router, prefix="/api/mcps", tags=["MCP Servers"])
        app.include_router(old_vmcp_router, prefix="/api/vmcps", tags=["vMCPs"])
        return app

    @pytest.fixture
    def new_app(self):
        """Create app with new routers"""
        app = FastAPI(title="New Router Test")
        app.include_router(new_mcp_router, prefix="/api/mcps", tags=["MCP Servers"])
        app.include_router(new_vmcp_router, prefix="/api/vmcps", tags=["vMCPs"])
        return app

    def test_schema_structure_compatibility(self, old_app, new_app):
        """Test that both apps generate compatible OpenAPI schemas"""
        old_schema = old_app.openapi()
        new_schema = new_app.openapi()
        
        # Both should have same basic structure
        assert "paths" in old_schema
        assert "paths" in new_schema
        assert "components" in old_schema
        assert "components" in new_schema
        
        print(f"📊 Old schema has {len(old_schema['paths'])} endpoints")
        print(f"📊 New schema has {len(new_schema['paths'])} endpoints")

    def test_endpoint_compatibility(self, old_app, new_app):
        """Test that both apps have the same endpoints"""
        old_schema = old_app.openapi()
        new_schema = new_app.openapi()
        
        old_paths = set(old_schema["paths"].keys())
        new_paths = set(new_schema["paths"].keys())
        
        print(f"🔍 Old paths: {sorted(old_paths)}")
        print(f"🔍 New paths: {sorted(new_paths)}")
        
        # Check for missing endpoints
        missing_in_new = old_paths - new_paths
        missing_in_old = new_paths - old_paths
        
        if missing_in_new:
            print(f"⚠️  Missing in new: {missing_in_new}")
        if missing_in_old:
            print(f"⚠️  Missing in old: {missing_in_old}")
        
        # For now, just log differences - we expect some differences
        print(f"📊 Endpoint compatibility: {len(old_paths & new_paths)}/{len(old_paths | new_paths)} common")

    def test_model_field_compatibility(self, old_app, new_app):
        """Test that models have compatible field structures"""
        old_schema = old_app.openapi()
        new_schema = new_app.openapi()
        
        old_models = old_schema.get("components", {}).get("schemas", {})
        new_models = new_schema.get("components", {}).get("schemas", {})
        
        print(f"📊 Old models: {len(old_models)}")
        print(f"📊 New models: {len(new_models)}")
        
        # Find common models
        common_models = set(old_models.keys()) & set(new_models.keys())
        print(f"📊 Common models: {len(common_models)}")
        
        # Check a few key models for field compatibility
        key_models = ["VMCPCreateRequest", "VMCPConfig", "MCPCreateRequest"]
        
        for model_name in key_models:
            if model_name in common_models:
                old_model = old_models[model_name]
                new_model = new_models[model_name]
                
                print(f"🔍 Comparing model: {model_name}")
                
                # Extract properties
                old_props = old_model.get("properties", {})
                new_props = new_model.get("properties", {})
                
                old_fields = set(old_props.keys())
                new_fields = set(new_props.keys())
                
                print(f"   Old fields: {sorted(old_fields)}")
                print(f"   New fields: {sorted(new_fields)}")
                
                # Check for field differences
                missing_in_new = old_fields - new_fields
                missing_in_old = new_fields - old_fields
                
                if missing_in_new:
                    print(f"   ⚠️  Missing in new: {missing_in_new}")
                if missing_in_old:
                    print(f"   ⚠️  Missing in old: {missing_in_old}")
                
                # Check field types
                common_fields = old_fields & new_fields
                for field in common_fields:
                    old_type = old_props[field].get("type")
                    new_type = new_props[field].get("type")
                    if old_type != new_type:
                        print(f"   ⚠️  Field '{field}' type changed: {old_type} -> {new_type}")

    def test_request_response_compatibility(self, old_app, new_app):
        """Test that request/response structures are compatible"""
        old_schema = old_app.openapi()
        new_schema = new_app.openapi()
        
        # Check a few key endpoints
        test_endpoints = [
            "/api/vmcps/create",
            "/api/mcps/install"
        ]
        
        for endpoint in test_endpoints:
            if endpoint in old_schema["paths"] and endpoint in new_schema["paths"]:
                print(f"🔍 Checking endpoint: {endpoint}")
                
                old_endpoint = old_schema["paths"][endpoint]
                new_endpoint = new_schema["paths"][endpoint]
                
                # Check POST method (most common for these endpoints)
                if "post" in old_endpoint and "post" in new_endpoint:
                    old_post = old_endpoint["post"]
                    new_post = new_endpoint["post"]
                    
                    # Check request body
                    if "requestBody" in old_post and "requestBody" in new_post:
                        old_req = old_post["requestBody"]["content"]["application/json"]["schema"]
                        new_req = new_post["requestBody"]["content"]["application/json"]["schema"]
                        
                        print(f"   Request schema refs: {old_req.get('$ref')} vs {new_req.get('$ref')}")
                    
                    # Check response
                    if "responses" in old_post and "responses" in new_post:
                        old_resp = old_post["responses"].get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
                        new_resp = new_post["responses"].get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
                        
                        print(f"   Response schema refs: {old_resp.get('$ref')} vs {new_resp.get('$ref')}")

    def test_actual_request_validation(self, old_app, new_app):
        """Test actual request validation with sample data"""
        old_client = TestClient(old_app)
        new_client = TestClient(new_app)
        
        # Test vMCP creation request
        vmcp_create_data = {
            "name": "test-vmcp",
            "description": "Test vMCP for compatibility",
            "system_prompt": "You are a helpful assistant"
        }
        
        print("🔍 Testing vMCP creation request validation...")
        
        # Test old router
        try:
            old_response = old_client.post("/api/vmcps/create", json=vmcp_create_data)
            print(f"   Old router response: {old_response.status_code}")
            if old_response.status_code != 200:
                print(f"   Old router error: {old_response.text}")
        except Exception as e:
            print(f"   Old router exception: {e}")
        
        # Test new router
        try:
            new_response = new_client.post("/api/vmcps/create", json=vmcp_create_data)
            print(f"   New router response: {new_response.status_code}")
            if new_response.status_code != 200:
                print(f"   New router error: {new_response.text}")
        except Exception as e:
            print(f"   New router exception: {e}")
        
        # Test MCP server installation request
        mcp_install_data = {
            "name": "test-server",
            "url": "http://localhost:8001/test/mcp",
            "transport_type": "http"
        }
        
        print("🔍 Testing MCP installation request validation...")
        
        # Test old router
        try:
            old_response = old_client.post("/api/mcps/install", json=mcp_install_data)
            print(f"   Old router response: {old_response.status_code}")
            if old_response.status_code != 200:
                print(f"   Old router error: {old_response.text}")
        except Exception as e:
            print(f"   Old router exception: {e}")
        
        # Test new router
        try:
            new_response = new_client.post("/api/mcps/install", json=mcp_install_data)
            print(f"   New router response: {new_response.status_code}")
            if new_response.status_code != 200:
                print(f"   New router error: {new_response.text}")
        except Exception as e:
            print(f"   New router exception: {e}")
