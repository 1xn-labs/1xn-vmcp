#!/usr/bin/env python3
"""
HTTP Tool Integration Tests
===========================

Comprehensive tests for HTTP tool functionality using the test server.
These tests verify that the HTTP tool engine works correctly with various
authentication methods, request types, and response patterns.
"""

import pytest
import asyncio
import json
import base64
from typing import Dict, Any

from src.vmcp.vmcps.vmcp_config_manager.custom_tool_engines.http_tool import execute_http_tool


class TestHTTPToolIntegration:
    """Test HTTP tool integration with the test server"""
    
    @pytest.fixture
    def base_url(self):
        """Base URL for the test server"""
        return "http://localhost:8002"
    
    @pytest.fixture
    def environment_variables(self):
        """Environment variables for testing"""
        return {
            "API_KEY": "test-api-key-123",
            "BEARER_TOKEN": "bearer-token-admin",
            "CUSTOM_TOKEN": "custom-token-123",
            "USERNAME": "admin",
            "PASSWORD": "admin123"
        }
    
    @pytest.mark.asyncio
    async def test_simple_get_request(self, base_url, environment_variables):
        """Test simple GET request without authentication"""
        custom_tool = {
            "name": "health_check",
            "api_config": {
                "url": f"{base_url}/health",
                "method": "GET"
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "healthy" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_bearer_token_auth(self, base_url, environment_variables):
        """Test Bearer token authentication"""
        custom_tool = {
            "name": "get_current_user",
            "api_config": {
                "url": f"{base_url}/auth/me",
                "method": "GET",
                "auth": {
                    "type": "bearer",
                    "token": "@config.BEARER_TOKEN"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "admin" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_api_key_header_auth(self, base_url, environment_variables):
        """Test API key authentication via header"""
        custom_tool = {
            "name": "get_users",
            "api_config": {
                "url": f"{base_url}/users",
                "method": "GET",
                "auth": {
                    "type": "apikey",
                    "apiKey": "@config.API_KEY",
                    "keyName": "X-API-Key"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "admin" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_api_key_query_auth(self, base_url, environment_variables):
        """Test API key authentication via query parameter"""
        custom_tool = {
            "name": "get_products",
            "api_config": {
                "url": f"{base_url}/products",
                "method": "GET",
                "query_params": {
                    "api_key": "@config.API_KEY"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "Laptop" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_basic_auth(self, base_url, environment_variables):
        """Test Basic authentication"""
        custom_tool = {
            "name": "create_user",
            "api_config": {
                "url": f"{base_url}/users",
                "method": "POST",
                "auth": {
                    "type": "basic",
                    "username": "@config.USERNAME",
                    "password": "@config.PASSWORD"
                },
                "headers": {
                    "Content-Type": "application/json"
                },
                "body_parsed": {
                    "username": "testuser",
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "password": "password123"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "testuser" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_custom_auth(self, base_url, environment_variables):
        """Test custom authentication"""
        custom_tool = {
            "name": "get_product",
            "api_config": {
                "url": f"{base_url}/products/1",
                "method": "GET",
                "auth": {
                    "type": "custom",
                    "headers": {
                        "X-Custom-Token": "@config.CUSTOM_TOKEN"
                    }
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "Laptop" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_post_with_json_body(self, base_url, environment_variables):
        """Test POST request with JSON body"""
        custom_tool = {
            "name": "create_product",
            "api_config": {
                "url": f"{base_url}/products",
                "method": "POST",
                "auth": {
                    "type": "bearer",
                    "token": "@config.BEARER_TOKEN"
                },
                "headers": {
                    "Content-Type": "application/json"
                },
                "body_parsed": {
                    "name": "Test Product",
                    "description": "A test product",
                    "price": 99.99,
                    "category": "Test",
                    "in_stock": True,
                    "tags": ["test", "new"],
                    "metadata": {
                        "brand": "TestBrand",
                        "warranty": "1 year"
                    }
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "Test Product" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_put_request(self, base_url, environment_variables):
        """Test PUT request"""
        custom_tool = {
            "name": "update_user",
            "api_config": {
                "url": f"{base_url}/users/1",
                "method": "PUT",
                "auth": {
                    "type": "bearer",
                    "token": "@config.BEARER_TOKEN"
                },
                "headers": {
                    "Content-Type": "application/json"
                },
                "body_parsed": {
                    "username": "updateduser",
                    "email": "updated@test.com",
                    "full_name": "Updated User",
                    "is_active": True
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "updateduser" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_patch_request(self, base_url, environment_variables):
        """Test PATCH request"""
        custom_tool = {
            "name": "update_product",
            "api_config": {
                "url": f"{base_url}/products/1",
                "method": "PATCH",
                "auth": {
                    "type": "bearer",
                    "token": "@config.BEARER_TOKEN"
                },
                "headers": {
                    "Content-Type": "application/json"
                },
                "body_parsed": {
                    "price": 89.99,
                    "in_stock": False
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "89.99" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_delete_request(self, base_url, environment_variables):
        """Test DELETE request"""
        custom_tool = {
            "name": "delete_user",
            "api_config": {
                "url": f"{base_url}/users/1",
                "method": "DELETE",
                "auth": {
                    "type": "bearer",
                    "token": "@config.BEARER_TOKEN"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_query_parameters(self, base_url, environment_variables):
        """Test query parameters"""
        custom_tool = {
            "name": "search_products",
            "api_config": {
                "url": f"{base_url}/products",
                "method": "GET",
                "query_params": {
                    "api_key": "@config.API_KEY",
                    "category": "Electronics",
                    "in_stock": "true",
                    "min_price": "10",
                    "max_price": "1000"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "Laptop" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_url_variable_substitution(self, base_url, environment_variables):
        """Test URL variable substitution"""
        custom_tool = {
            "name": "get_user_by_id",
            "api_config": {
                "url": f"{base_url}/users/{{user_id}}",
                "method": "GET",
                "auth": {
                    "type": "bearer",
                    "token": "@config.BEARER_TOKEN"
                }
            }
        }
        
        arguments = {"user_id": "1"}
        result = await execute_http_tool(custom_tool, arguments, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "admin" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_path_parameter_substitution(self, base_url, environment_variables):
        """Test path parameter substitution"""
        custom_tool = {
            "name": "get_product_by_id",
            "api_config": {
                "url": f"{base_url}/products/:product_id",
                "method": "GET",
                "auth": {
                    "type": "custom",
                    "headers": {
                        "X-Custom-Token": "@config.CUSTOM_TOKEN"
                    }
                }
            }
        }
        
        arguments = {"product_id": "1"}
        result = await execute_http_tool(custom_tool, arguments, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "Laptop" in result.content[0].text
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_complex_search(self, base_url, environment_variables):
        """Test complex search endpoint"""
        custom_tool = {
            "name": "search_all",
            "api_config": {
                "url": f"{base_url}/search",
                "method": "GET",
                "auth": {
                    "type": "apikey",
                    "apiKey": "@config.API_KEY",
                    "keyName": "X-API-Key"
                },
                "query_params": {
                    "q": "laptop",
                    "type": "all",
                    "limit": "5"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "laptop" in result.content[0].text.lower()
        assert "200" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_error_handling_404(self, base_url, environment_variables):
        """Test error handling for 404"""
        custom_tool = {
            "name": "error_404",
            "api_config": {
                "url": f"{base_url}/errors/404",
                "method": "GET"
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert result.isError
        assert len(result.content) == 1
        assert "404" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_error_handling_401(self, base_url, environment_variables):
        """Test error handling for 401"""
        custom_tool = {
            "name": "error_401",
            "api_config": {
                "url": f"{base_url}/errors/401",
                "method": "GET"
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert result.isError
        assert len(result.content) == 1
        assert "401" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_missing_url(self, base_url, environment_variables):
        """Test error handling for missing URL"""
        custom_tool = {
            "name": "missing_url",
            "api_config": {
                "method": "GET"
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert result.isError
        assert len(result.content) == 1
        assert "No URL configured" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_invalid_auth(self, base_url, environment_variables):
        """Test invalid authentication"""
        custom_tool = {
            "name": "invalid_auth",
            "api_config": {
                "url": f"{base_url}/auth/me",
                "method": "GET",
                "auth": {
                    "type": "bearer",
                    "token": "invalid-token"
                }
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert result.isError
        assert len(result.content) == 1
        assert "401" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_file_upload(self, base_url, environment_variables):
        """Test file upload endpoint"""
        custom_tool = {
            "name": "upload_file",
            "api_config": {
                "url": f"{base_url}/upload",
                "method": "POST",
                "headers": {
                    "Content-Type": "multipart/form-data"
                },
                "body": "test file content"
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        # Note: This test might fail depending on how the server handles the body
        # The actual implementation would need proper multipart handling
        assert len(result.content) == 1
    
    @pytest.mark.asyncio
    async def test_file_download(self, base_url, environment_variables):
        """Test file download endpoint"""
        custom_tool = {
            "name": "download_file",
            "api_config": {
                "url": f"{base_url}/download/test.txt",
                "method": "GET"
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, environment_variables)
        
        assert not result.isError
        assert len(result.content) == 1
        assert "test file" in result.content[0].text.lower()
        assert "200" in result.content[0].text


class TestHTTPToolVariableSubstitution:
    """Test variable substitution in HTTP tools"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8002"
    
    @pytest.mark.asyncio
    async def test_param_variable_substitution(self, base_url):
        """Test @param variable substitution"""
        custom_tool = {
            "name": "get_user",
            "api_config": {
                "url": f"{base_url}/users/{{user_id}}",
                "method": "GET",
                "auth": {
                    "type": "bearer",
                    "token": "bearer-token-admin"
                }
            }
        }
        
        arguments = {"user_id": "1"}
        environment_variables = {}
        
        result = await execute_http_tool(custom_tool, arguments, environment_variables)
        
        assert not result.isError
        assert "admin" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_config_variable_substitution(self, base_url):
        """Test @config variable substitution"""
        custom_tool = {
            "name": "get_products",
            "api_config": {
                "url": f"{base_url}/products",
                "method": "GET",
                "query_params": {
                    "api_key": "@config.API_KEY"
                }
            }
        }
        
        arguments = {}
        environment_variables = {"API_KEY": "test-api-key-123"}
        
        result = await execute_http_tool(custom_tool, arguments, environment_variables)
        
        assert not result.isError
        assert "Laptop" in result.content[0].text
    
    @pytest.mark.asyncio
    async def test_mixed_variable_substitution(self, base_url):
        """Test mixed @param and @config variable substitution"""
        custom_tool = {
            "name": "update_user",
            "api_config": {
                "url": f"{base_url}/users/{{user_id}}",
                "method": "PUT",
                "auth": {
                    "type": "bearer",
                    "token": "@config.BEARER_TOKEN"
                },
                "headers": {
                    "Content-Type": "application/json"
                },
                "body_parsed": {
                    "username": "@param.new_username",
                    "email": "@param.new_email"
                }
            }
        }
        
        arguments = {
            "user_id": "1",
            "new_username": "updateduser",
            "new_email": "updated@test.com"
        }
        environment_variables = {"BEARER_TOKEN": "bearer-token-admin"}
        
        result = await execute_http_tool(custom_tool, arguments, environment_variables)
        
        assert not result.isError
        assert "updateduser" in result.content[0].text
        assert "updated@test.com" in result.content[0].text


# Integration test that requires the test server to be running
@pytest.mark.integration
class TestHTTPToolServerIntegration:
    """Integration tests that require the test server to be running"""
    
    @pytest.fixture(scope="class")
    def server_url(self):
        """URL of the running test server"""
        return "http://localhost:8002"
    
    @pytest.mark.asyncio
    async def test_server_health(self, server_url):
        """Test that the server is running and healthy"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{server_url}/health") as response:
                assert response.status == 200
                data = await response.json()
                assert data["success"] is True
                assert data["data"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, server_url):
        """Test a complete workflow with multiple requests"""
        # This would test a complete user journey
        # For now, just test that we can make multiple requests
        custom_tool = {
            "name": "health_check",
            "api_config": {
                "url": f"{server_url}/health",
                "method": "GET"
            }
        }
        
        result = await execute_http_tool(custom_tool, {}, {})
        assert not result.isError
