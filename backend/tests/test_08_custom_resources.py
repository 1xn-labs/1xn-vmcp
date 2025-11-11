"""
Test Suite 8: Custom Resources
Tests custom resource creation, reading, and integration with prompts and tools
"""

import pytest
import requests
import tempfile
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.mark.resources
class TestCustomResources:
    """Test custom resources functionality"""

    def test_create_custom_resource_file(self, base_url, create_vmcp, helpers):
        """Test 8.1: Create a custom resource from file upload"""
        vmcp = create_vmcp
        print(f"\n📦 Test 8.1 - Creating custom resource from file: {vmcp['id']}")

        # Create a test file
        test_content = "This is a test document for resource testing."
        
        # Upload the file as a resource using the correct blob endpoint
        files = {'file': ('test_document.txt', test_content.encode(), 'text/plain')}
        data = {'vmcp_id': vmcp['id']}
        
        response = requests.post(
            base_url + "api/blob/upload",
            files=files,
            data=data
        )

        assert response.status_code == 200
        response_data = response.json()
        assert "blob_id" in response_data
        assert response_data["original_name"] == "test_document.txt"
        assert response_data["vmcp_id"] == vmcp["id"]

        # Verify the resource was added to vMCP
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        assert len(updated_vmcp["custom_resources"]) >= 1
        
        # Find our resource
        test_resource = None
        for resource in updated_vmcp["custom_resources"]:
            if resource.get("original_filename") == "test_document.txt":
                test_resource = resource
                break
        
        assert test_resource is not None
        assert test_resource["original_filename"] == "test_document.txt"

        print("✅ Custom resource created from file upload")

    def test_create_custom_resource_text(self, base_url, create_vmcp, helpers):
        """Test 8.2: Create a custom resource with text content"""
        vmcp = create_vmcp
        print(f"\n📦 Test 8.2 - Creating custom resource with text content: {vmcp['id']}")

        # Create text resource directly
        text_content = "# API Documentation\n\nThis is sample API documentation content."
        
        files = {'file': ('api_docs.md', text_content.encode(), 'text/markdown')}
        data = {'vmcp_id': vmcp['id']}
        
        response = requests.post(
            base_url + "api/blob/upload",
            files=files,
            data=data
        )

        assert response.status_code == 200
        response_data = response.json()
        assert "blob_id" in response_data
        assert response_data["original_name"] == "api_docs.md"

        # Verify the resource
        updated_vmcp = helpers["get_vmcp"](vmcp["id"])
        api_resource = None
        for resource in updated_vmcp["custom_resources"]:
            if resource.get("original_filename") == "api_docs.md":
                api_resource = resource
                break
        
        assert api_resource is not None
        assert api_resource["original_filename"] == "api_docs.md"
        assert api_resource["content_type"] == "text/markdown"

        print("✅ Custom text resource created successfully")

    @pytest.mark.asyncio
    async def test_list_custom_resources_via_mcp(self, base_url, create_vmcp, helpers):
        """Test 8.3: List custom resources via MCP"""
        vmcp = create_vmcp
        print(f"\n📦 Test 8.3 - Listing custom resources via MCP: {vmcp['id']}")

        # First add a custom resource
        test_content = "Resource content for MCP listing test"
        files = {'file': ('mcp_test.txt', test_content.encode(), 'text/plain')}
        data = {'vmcp_id': vmcp['id']}
        
        response = requests.post(
            base_url + "api/blob/upload",
            files=files,
            data=data
        )
        assert response.status_code == 200

        # Connect via MCP and list resources
        mcp_url = f"{base_url}private/{vmcp['name']}/vmcp"

        async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List resources
                resources_response = await session.list_resources()
                resource_uris = [resource.uri for resource in resources_response.resources]

                print(f"📋 Available resources: {resource_uris}")

                # Look for our custom resource
                custom_resource_found = False
                for uri in resource_uris:
                    uri_str = str(uri)
                    if "mcp_test" in uri_str or "mcp_test.txt" in uri_str:
                        custom_resource_found = True
                        break

                assert custom_resource_found, "Custom resource should be listed in MCP resources"

                print("✅ Custom resource listed successfully via MCP")