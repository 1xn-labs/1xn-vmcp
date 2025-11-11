import pytest
import requests
import random
import uuid
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

class TestVMCPFlow:
    """Test VMCP creation and MCP server addition flow"""
    
    base_url = "http://localhost:8000/"
    uuid_string = str(uuid.uuid4())
    vmcp_name=f"flow_test_vmcp_{uuid_string[0:12]}"

    
    @pytest.fixture(scope="class")
    def created_vmcp(self):
        """Create a VMCP for testing (runs once per test class)"""
        print("\nCreating VMCP...")

        uuid_string = str(uuid.uuid4())
        vmcp_name=f"flow_test_vmcp_{uuid_string[0:12]}"

        response = requests.post(
            self.base_url + "api/vmcps/create",
            json={
                "name": self.vmcp_name,
                "description": "VMCP for testing flow",
                # "system_prompt": "You are a helpful asssistant",
            }
        )

        assert response.status_code == 200
        vmcp_data = response.json()["vMCP"]

        print(f"✅ Created VMCP '{vmcp_name}' with ID: {vmcp_data['id']}")

        yield vmcp_data  # Provide the vmcp data to tests

        # Cleanup after all tests in the class complete
        try:
            delete_response = requests.delete(self.base_url + f"api/vmcps/{vmcp_data['id']}")
            if delete_response.status_code == 200:
                print(f"🗑️  Deleted test vMCP: {vmcp_data['id']}")
        except Exception as e:
            print(f"⚠️  Failed to delete vMCP {vmcp_data['id']}: {e}")
    
    def test_1_vmcp_creation(self, created_vmcp):
        """Test that VMCP was created properly"""
        print(f"\n📦 Test 1 - Checking VMCP: {created_vmcp['id']}")
        
        # Test basic structure - don't check specific name since it's random
        assert created_vmcp["name"] == self.vmcp_name  # Starts with our prefix
        assert created_vmcp["description"] == "VMCP for testing flow"
        assert "id" in created_vmcp
        assert created_vmcp["system_prompt"] is None

        # assert created_vmcp["system_prompt"] is not None, f"System prompt is: {created_vmcp['system_prompt']}"
        
        print("✅ VMCP creation test passed")
    
    def test_2_add_mcp_server(self, created_vmcp):
        """Test adding an MCP server to the VMCP"""
        vmcp_id = created_vmcp["id"]
        
        print(f"\n📦 Test 2 - Adding server to VMCP: {vmcp_id}")
        
        server_data = {
            "server_data": {
                "name": "kite",
                "url": "https://mcp.kite.trade/mcp",
                "transport": "http",
                "description": "Test MCP Server"
            }
        }
        
        response = requests.post(
            self.base_url + f"api/vmcps/{vmcp_id}/add-server",
            json=server_data
        )
        
        assert response.status_code == 200
        server_response = response.json()
        
        # Check that server was added successfully
        assert "server" in server_response or "success" in server_response
        
        print("✅ MCP server addition test passed")
    
    def test_3_add_custom_prompt(self, created_vmcp):
        """Test adding a custom prompt to the VMCP"""
        vmcp_id = created_vmcp["id"]
        
        print(f"\n📦 Test 3 - Adding custom prompt to VMCP: {vmcp_id}")
        
        # Step 1: Get VMCP details
        get_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert get_response.status_code == 200
        vmcp_details = get_response.json()
        
        print(f"📋 Current custom prompts: {len(vmcp_details['custom_prompts'])}")
        
        # Step 2: Add custom prompt
        custom_prompt_dict = {
            "name": "test_prompt", 
            "description": "", 
            "text": "This is a simple text test prompt", 
            "variables": [], 
            "environment_variables": [],
            "tool_calls": []
        }
        
        vmcp_details['custom_prompts'].append(custom_prompt_dict)
        
        # Step 3: Update VMCP
        update_response = requests.put(
            self.base_url + f"api/vmcps/{vmcp_id}",
            json=vmcp_details
        )
        assert update_response.status_code == 200
        
        # Step 4: Verify prompt was added
        verify_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert verify_response.status_code == 200
        updated_vmcp = verify_response.json()
        
        # Check that prompt was added
        assert len(updated_vmcp['custom_prompts']) == 1
        assert updated_vmcp['custom_prompts'][0]['name'] == "test_prompt"
        assert updated_vmcp['custom_prompts'][0]['text'] == "This is a simple text test prompt"
        
        print("✅ Custom prompt addition test passed")
    
    def test_4_add_custom_tool(self, created_vmcp):
        """Test adding a custom tool to the VMCP"""
        vmcp_id = created_vmcp["id"]
        
        print(f"\n📦 Test 4 - Adding custom tool to VMCP: {vmcp_id}")
        
        # Step 1: Get VMCP details
        get_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert get_response.status_code == 200
        vmcp_details = get_response.json()
        
        print(f"🔧 Current custom tools: {len(vmcp_details['custom_tools'])}")
        
        # Step 2: Add custom tool
        custom_tool_dict = {
            "atomic_blocks": [],
            "description": "",
            "environment_variables": [],
            "name": "simple_custom_tool",
            "text": "this is a simple custom tool",
            "tool_calls": [],
            "tool_type": "prompt",
            "variables": []
        }
        
        vmcp_details['custom_tools'].append(custom_tool_dict)
        
        # Step 3: Update VMCP
        update_response = requests.put(
            self.base_url + f"api/vmcps/{vmcp_id}",
            json=vmcp_details
        )
        assert update_response.status_code == 200
        
        # Step 4: Verify tool was added
        verify_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert verify_response.status_code == 200
        updated_vmcp = verify_response.json()
        
        # Check that tool was added
        assert len(updated_vmcp['custom_tools']) == 1
        assert updated_vmcp['custom_tools'][0]['name'] == "simple_custom_tool"
        assert updated_vmcp['custom_tools'][0]['tool_type'] == "prompt"
        assert updated_vmcp['custom_tools'][0]['text'] == "this is a simple custom tool"
        
        print("✅ Custom tool addition test passed")
    
    def test_5_add_prompt_with_tool_call(self, created_vmcp):
        """Test adding a custom prompt with tool call to the VMCP"""
        vmcp_id = created_vmcp["id"]
        
        print(f"\n📦 Test 5 - Adding prompt with tool call to VMCP: {vmcp_id}")
        
        # Step 1: Get VMCP details
        get_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert get_response.status_code == 200
        vmcp_details = get_response.json()
        
        print(f"📋 Current custom prompts: {len(vmcp_details['custom_prompts'])}")
        
        # Step 2: Add custom prompt with tool call
        custom_prompt_dict = {
            "description": "",
            "environment_variables": [],
            "name": "prompt_with_tool",
            "text": "@tool.Kite.login()",
            "tool_calls": [],
            "variables": []
        }
        
        vmcp_details['custom_prompts'].append(custom_prompt_dict)
        
        # Step 3: Update VMCP
        update_response = requests.put(
            self.base_url + f"api/vmcps/{vmcp_id}",
            json=vmcp_details
        )
        assert update_response.status_code == 200
        
        # Step 4: Verify prompt was added
        verify_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert verify_response.status_code == 200
        updated_vmcp = verify_response.json()
        
        # Check that second prompt was added (should have 2 prompts now)
        assert len(updated_vmcp['custom_prompts']) == 2
        
        # Find the new prompt (should be the second one)
        new_prompt = updated_vmcp['custom_prompts'][1]
        assert new_prompt['name'] == "prompt_with_tool"
        assert new_prompt['text'] == "@tool.Kite.login()"
        
        print("✅ Prompt with tool call addition test passed")
    
    def test_6_add_prompt_with_variable(self, created_vmcp):
        """Test adding a custom prompt with variables to the VMCP"""
        vmcp_id = created_vmcp["id"]
        
        print(f"\n📦 Test 6 - Adding prompt with variable to VMCP: {vmcp_id}")
        
        # Step 1: Get VMCP details
        get_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert get_response.status_code == 200
        vmcp_details = get_response.json()
        
        print(f"📋 Current custom prompts: {len(vmcp_details['custom_prompts'])}")
        
        # Step 2: Add custom prompt with variable
        custom_prompt_dict = {
            "name": "prompt_with_variable",
            "description": "",
            "text": "greet user in @param.lang",
            "environment_variables": [],
            "tool_calls": [],
            "variables": [
                {
                    "name": "lang",
                    "description": "Greet user in language", 
                    "required": False
                }
            ]
        }
        
        vmcp_details['custom_prompts'].append(custom_prompt_dict)
        
        # Step 3: Update VMCP
        update_response = requests.put(
            self.base_url + f"api/vmcps/{vmcp_id}",
            json=vmcp_details
        )
        assert update_response.status_code == 200
        
        # Step 4: Verify prompt was added
        verify_response = requests.get(self.base_url + f"api/vmcps/{vmcp_id}")
        assert verify_response.status_code == 200
        updated_vmcp = verify_response.json()
        
        # Check that third prompt was added (should have 3 prompts now)
        assert len(updated_vmcp['custom_prompts']) == 3
        
        # Find the new prompt (should be the third one)
        new_prompt = updated_vmcp['custom_prompts'][2]
        assert new_prompt['name'] == "prompt_with_variable"
        assert new_prompt['text'] == "greet user in @param.lang"
        assert len(new_prompt['variables']) == 1
        
        # Check the variable structure
        variable = new_prompt['variables'][0]
        assert variable['name'] == "lang"
        assert variable['description'] == "Greet user in language"
        assert variable['required'] == False
        
        print("✅ Prompt with variable addition test passed")
    
    def test_7_verify_mcp_client_access(self, created_vmcp):
        """Test that tools and prompts are accessible via MCP client"""
        vmcp_id = created_vmcp["id"]
        vmcp_name = created_vmcp["name"]
        
        print(f"\n📦 Test 7 - Verifying MCP client access for VMCP: {vmcp_id}")
        
        # Construct the MCP server URL
        mcp_url = f"{self.base_url}private/{vmcp_name}/vmcp"
        print(f"🔗 MCP URL: {mcp_url}")
        
        async def verify_mcp_access():
            try:
                # Connect to the MCP server
                async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        # Initialize the connection
                        await session.initialize()
                        
                        # List available tools
                        tools_response = await session.list_tools()
                        tool_names = [tool.name for tool in tools_response.tools]
                        print(f"🔧 Available tools: {tool_names}")
                        
                        # List available prompts  
                        prompts_response = await session.list_prompts()
                        prompt_names = [prompt.name for prompt in prompts_response.prompts]
                        print(f"📋 Available prompts: {prompt_names}")
                        
                        return tool_names, prompt_names
                        
            except Exception as e:
                print(f"❌ MCP connection failed: {e}")
                return [], []
        
        # Run the async function
        tool_names, prompt_names = asyncio.run(verify_mcp_access())
        
        # Assert our custom items are present
        # Custom tool should be available
        assert "simple_custom_tool" in tool_names, f"simple_custom_tool not found in {tool_names}"
        
        # Custom prompts should be available
        assert "test_prompt" in prompt_names, f"test_prompt not found in {prompt_names}"
        assert "prompt_with_tool" in prompt_names, f"prompt_with_tool not found in {prompt_names}" 
        assert "prompt_with_variable" in prompt_names, f"prompt_with_variable not found in {prompt_names}"
        
        print("✅ MCP client verification test passed")