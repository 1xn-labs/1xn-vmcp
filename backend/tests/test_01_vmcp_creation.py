"""
Test Suite 1: vMCP Creation
Tests basic vMCP creation and validation
"""

import uuid

import pytest
import requests


@pytest.mark.vmcp_creation
class TestVMCPCreation:
    """Test vMCP creation functionality"""

    def test_create_vmcp_basic(self, base_url, vmcp_name, helpers):
        """Test 1.1: Create a basic vMCP"""
        print(f"\n📦 Test 1.1 - Creating vMCP: {vmcp_name}")

        response = requests.post(
            base_url + "api/vmcps/create",
            json={
                "name": vmcp_name,
                "description": "Test vMCP for basic creation"
            }
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "vMCP" in data, "Response should contain 'vMCP' key"

        vmcp = data["vMCP"]
        assert vmcp["name"] == vmcp_name, f"Expected name '{vmcp_name}', got '{vmcp['name']}'"
        assert vmcp["description"] == "Test vMCP for basic creation"
        assert "id" in vmcp, "vMCP should have an ID"
        assert vmcp["system_prompt"] is None, "System prompt should be None by default"
        assert vmcp["custom_prompts"] == [], "Custom prompts should be empty list"
        assert vmcp["custom_tools"] == [], "Custom tools should be empty list"
        assert vmcp["custom_resources"] == [], "Custom resources should be empty list"

        print(f"✅ vMCP created with ID: {vmcp['id']}")

        # Cleanup
        helpers["delete_vmcp"](vmcp["id"])

    def test_create_vmcp_with_system_prompt(self, base_url, helpers):
        """Test 1.2: Create vMCP with system prompt"""
        vmcp_name = f"test_vmcp_{uuid.uuid4().hex[:12]}"
        print(f"\n📦 Test 1.2 - Creating vMCP with system prompt: {vmcp_name}")

        system_prompt = {
            "text": "You are a helpful assistant",
            "variables": []
        }

        response = requests.post(
            base_url + "api/vmcps/create",
            json={
                "name": vmcp_name,
                "description": "Test vMCP with system prompt",
                "system_prompt": system_prompt
            }
        )

        assert response.status_code == 200
        data = response.json()
        vmcp = data["vMCP"]

        assert vmcp["system_prompt"] is not None
        assert vmcp["system_prompt"]["text"] == "You are a helpful assistant"
        print("✅ vMCP created with system prompt")

        # Cleanup
        helpers["delete_vmcp"](vmcp["id"])

    def test_get_vmcp_details(self, base_url, create_vmcp):
        """Test 1.3: Retrieve vMCP details"""
        vmcp = create_vmcp
        print(f"\n📦 Test 1.3 - Retrieving vMCP details: {vmcp['id']}")

        response = requests.get(base_url + f"api/vmcps/{vmcp['id']}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == vmcp["id"]
        assert data["name"] == vmcp["name"]
        assert "created_at" in data
        assert "updated_at" in data

        print("✅ vMCP details retrieved successfully")

    def test_list_vmcps(self, base_url, create_vmcp):
        """Test 1.4: List all vMCPs"""
        print("\n📦 Test 1.4 - Listing all vMCPs")

        response = requests.get(base_url + "api/vmcps/list")

        assert response.status_code == 200
        data = response.json()

        # Response has 'private' and 'public' keys
        assert "private" in data or "public" in data or "vmcps" in data or isinstance(data, list)
        total_vmcps = len(data['private']) + len(data['public']) if 'private' in data and 'public' in data else (len(data) if isinstance(data, list) else len(data.get('vmcps', [])))
        print(f"✅ Found {total_vmcps} vMCPs")

    def test_update_vmcp_description(self, base_url, create_vmcp, helpers):
        """Test 1.5: Update vMCP description"""
        vmcp = create_vmcp
        print(f"\n📦 Test 1.5 - Updating vMCP description: {vmcp['id']}")

        # Get current vMCP data
        vmcp_data = helpers["get_vmcp"](vmcp["id"])

        # Update description
        new_description = "Updated test description"
        vmcp_data["description"] = new_description

        # Update vMCP
        updated = helpers["update_vmcp"](vmcp["id"], vmcp_data)

        # Verify update (update endpoint returns {"success": True, "vMCP": {...}})
        assert updated["success"]
        assert updated["vMCP"]["description"] == new_description
        print("✅ vMCP description updated successfully")
