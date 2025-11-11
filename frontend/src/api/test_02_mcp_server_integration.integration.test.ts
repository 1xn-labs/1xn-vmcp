/**
 * Integration Test Suite 2: MCP Server Integration
 * Tests MCP server installation, connection, and tool/resource/prompt access with REAL API calls
 * 
 * Requires: 
 * - Backend server running on localhost:8000
 * - MCP test servers running on localhost:8001
 * 
 * Corresponds to: backend/tests/test_02_mcp_server_integration.py
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { apiClient } from './client'
import {
  setupIntegrationTests,
  requireBackend,
  createVMCPForTest,
  createMCPServerForTest,
  wait,
} from '../test/integration-setup'
import { generateVMCPName, MCP_SERVERS } from '../test/test-setup'

// Setup integration test environment
setupIntegrationTests()

describe('Integration Test Suite 2: MCP Server Integration', () => {
  let createdVMCP: Awaited<ReturnType<typeof createVMCPForTest>>

  beforeAll(async () => {
    // Ensure backend is available
    await requireBackend()
    // Create a vMCP for all tests in this suite
    createdVMCP = await createVMCPForTest(generateVMCPName())
  })

  describe('Test 2.1: Add everything server to vMCP', () => {
    it('should add an everything server to vMCP', async () => {
      console.log('\n📦 Test 2.1 - Adding everything server to vMCP')

      // Add server directly to vMCP (matching frontend behavior from MCPServersTab)
      const serverData = {
        name: 'everything',
        url: MCP_SERVERS.everything,
        transport: 'http',
        description: 'Test everything MCP Server',
      }

      const addResult = await apiClient.addServerToVMCP(createdVMCP.id, serverData)

      expect(addResult.success).toBe(true)
      console.log('✅ Everything server added to vMCP')
    })
  })

  describe('Test 2.2: Add allfeature server to vMCP', () => {
    it('should add an allfeature server to vMCP', async () => {
      console.log('\n📦 Test 2.2 - Adding allfeature server to vMCP')

      // Add server directly to vMCP (matching frontend behavior from MCPServersTab)
      const serverData = {
        name: 'allfeature',
        url: MCP_SERVERS.allfeature,
        transport: 'http',
        description: 'Test allfeature MCP Server',
      }

      const addResult = await apiClient.addServerToVMCP(createdVMCP.id, serverData)

      expect(addResult.success).toBe(true)
      console.log('✅ AllFeature server added to vMCP')
    })
  })

  describe('Test 2.3: Verify tools from MCP server', () => {
    it('should list tools from a connected MCP server via vMCP', async () => {
      console.log('\n📦 Test 2.3 - Verifying tools from MCP server')

      // Wait for servers from previous tests to be ready
      await wait(500)

      // List tools from vMCP (which includes tools from servers added in Test 2.1 and 2.2)
      const result = await apiClient.listVMCPTools(createdVMCP.id)

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()

      const tools = result.data?.tools || []
      // Verify some expected tools exist (tools are prefixed with server name)
      const toolNames = tools.map((t: any) => t.name)
      expect(toolNames.some((name: string) => name.includes('create_task'))).toBe(true)

      console.log(`✅ Listed ${tools.length} tools from server via vMCP`)
    })
  })

  describe('Test 2.4: Verify prompts from MCP server', () => {
    it('should list prompts from a connected MCP server via vMCP', async () => {
      console.log('\n📦 Test 2.4 - Verifying prompts from MCP server')

      // Add server to vMCP
      const serverData = {
        name: 'allfeature',
        url: MCP_SERVERS.allfeature,
        transport: 'http',
        description: 'Test allfeature MCP Server',
      }

      const addResult = await apiClient.addServerToVMCP(createdVMCP.id, serverData)
      expect(addResult.success).toBe(true)
      await wait(500) // Wait for server to be added and connected

      // List prompts from vMCP (which includes prompts from the server)
      const result = await apiClient.listVMCPPrompts(createdVMCP.id)

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()

      const prompts = Array.isArray(result.data) ? result.data : []
      console.log(`✅ Listed ${prompts.length} prompts from server via vMCP`)
    })
  })

  describe('Test 2.5: Verify resources from MCP server', () => {
    it('should list resources from a connected MCP server via vMCP', async () => {
      console.log('\n📦 Test 2.5 - Verifying resources from MCP server')

      // Add server to vMCP
      const serverData = {
        name: 'allfeature',
        url: MCP_SERVERS.allfeature,
        transport: 'http',
        description: 'Test allfeature MCP Server',
      }

      const addResult = await apiClient.addServerToVMCP(createdVMCP.id, serverData)
      expect(addResult.success).toBe(true)
      await wait(500) // Wait for server to be added and connected

      // List resources from vMCP (which includes resources from the server)
      const result = await apiClient.listVMCPResources(createdVMCP.id)

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()

      const resources = Array.isArray(result.data) ? result.data : []
      console.log(`✅ Listed ${resources.length} resources from server via vMCP`)
    })
  })

  describe('Test 2.6: Call MCP tool', () => {
    it('should call a tool on an MCP server', async () => {
      console.log('\n📦 Test 2.6 - Calling MCP tool')

      // Create server using helper (registers for automatic cleanup)
      const serverId = await createMCPServerForTest({
        name: `test-server-${Date.now()}`,
        url: MCP_SERVERS.everything,
        mode: 'http',
      })

      const connectResult = await apiClient.connectMCPServer(serverId)
      expect(connectResult.success).toBe(true)
      await wait(500)

      // List tools first to find available tool
      const toolsResult = await apiClient.listMCPServerTools(serverId)
      expect(toolsResult.success).toBe(true)

      if (toolsResult.data) {
        const tools = (toolsResult.data as any)?.tools || (toolsResult.data as any)?.data?.tools || []
        if (tools.length > 0) {
          const toolName = tools[0].name

          const result = await apiClient.callMCPTool(serverId, {
            tool_name: toolName,
            arguments: {},
          })

          expect(result.success).toBe(true)
          expect(result.data).toBeDefined()

          console.log(`✅ Called tool: ${toolName}`)
        }
      }

      // Cleanup handled by createMCPServerForTest
    })
  })
})

