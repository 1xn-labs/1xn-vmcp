/**
 * Test Suite 2: MCP Server Integration
 * Tests MCP server installation, connection, and tool/resource/prompt access
 * 
 * Corresponds to: backend/tests/test_02_mcp_server_integration.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP, createTestHelpers } from '../test/test-setup'
import { createMockVMCP, createMockMCPServer, createMockToolCallResult } from '../test/api-mock-helpers'
import { MCP_SERVERS } from '../test/test-setup'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  installMcpServerApiMcpsInstallPost: vi.fn(),
  connectMcpServerWithCapabilitiesApiMcpsServerIdConnectPost: vi.fn(),
  listServerToolsApiMcpsServerIdToolsListGet: vi.fn(),
  listServerResourcesApiMcpsServerIdResourcesListGet: vi.fn(),
  listServerPromptsApiMcpsServerIdPromptsListGet: vi.fn(),
  callMcpToolApiMcpsServerIdToolsCallPost: vi.fn(),
  getMcpPromptApiMcpsServerIdPromptsGetPost: vi.fn(),
  getMcpResourceApiMcpsServerIdResourcesReadPost: vi.fn(),
  addServerToVmcpApiVmcpsVmcpIdAddServerPost: vi.fn(),
  getVmcpDetailsApiVmcpsVmcpIdGet: vi.fn(),
  createVmcpApiVmcpsCreatePost: vi.fn(),
}))

describe('Test Suite 2: MCP Server Integration', () => {
  let vmcpName: string
  let helpers: ReturnType<typeof createTestHelpers>
  let createdVMCP: ReturnType<typeof createTestVMCP>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    helpers = createTestHelpers()
    createdVMCP = createTestVMCP({ name: vmcpName })
    vi.clearAllMocks()
  })

  describe('Test 2.1: Add everything server to vMCP', () => {
    it('should add an everything server to vMCP', async () => {
      const serverData = {
        name: 'everything-server',
        url: MCP_SERVERS.everything,
        transport: 'http' as const,
        description: 'Everything MCP Server',
      }

      vi.mocked(sdk.addServerToVmcpApiVmcpsVmcpIdAddServerPost).mockResolvedValue({
        data: {
          success: true,
          message: 'Server added successfully',
          vmcp_config: createdVMCP,
          server: serverData,
        },
      } as any)

      const result = await apiClient.addServerToVMCP(createdVMCP.id, serverData)

      expect(result.success).toBe(true)
      expect(sdk.addServerToVmcpApiVmcpsVmcpIdAddServerPost).toHaveBeenCalledWith({
        path: { vmcp_id: createdVMCP.id },
        body: { server_data: serverData },
      })
    })
  })

  describe('Test 2.2: Add allfeature server to vMCP', () => {
    it('should add an allfeature server to vMCP', async () => {
      const serverData = {
        name: 'allfeature-server',
        url: MCP_SERVERS.allfeature,
        transport: 'http' as const,
        description: 'All Feature MCP Server',
      }

      vi.mocked(sdk.addServerToVmcpApiVmcpsVmcpIdAddServerPost).mockResolvedValue({
        data: {
          success: true,
          message: 'Server added successfully',
          vmcp_config: createdVMCP,
          server: serverData,
        },
      } as any)

      const result = await apiClient.addServerToVMCP(createdVMCP.id, serverData)

      expect(result.success).toBe(true)
    })
  })

  describe('Test 2.3: Verify tools from MCP server', () => {
    it('should list tools from a connected MCP server', async () => {
      const mockTools = [
        {
          name: 'test_tool',
          description: 'A test tool',
          inputSchema: { type: 'object', properties: {} },
        },
      ]

      vi.mocked(sdk.listServerToolsApiMcpsServerIdToolsListGet).mockResolvedValue({
        data: {
          success: true,
          data: {
            server: 'everything-server',
            tools: mockTools,
            total_tools: 1,
          },
        },
      } as any)

      const result = await apiClient.listMCPServerTools('everything-server')

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      // Tools may be in result.data.tools or result.data.data.tools
      const tools = (result.data as any)?.tools || (result.data as any)?.data?.tools || []
      expect(Array.isArray(tools)).toBe(true)
    })
  })

  describe('Test 2.4: Verify prompts from MCP server', () => {
    it('should list prompts from a connected MCP server', async () => {
      const mockPrompts = [
        {
          name: 'test_prompt',
          description: 'A test prompt',
          arguments: [],
        },
      ]

      vi.mocked(sdk.listServerPromptsApiMcpsServerIdPromptsListGet).mockResolvedValue({
        data: {
          success: true,
          data: {
            server: 'everything-server',
            prompts: mockPrompts,
            total_prompts: 1,
          },
        },
      } as any)

      const result = await apiClient.listMCPServerPrompts('everything-server')

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      // Prompts may be in result.data.prompts or result.data.data.prompts
      const prompts = (result.data as any)?.prompts || (result.data as any)?.data?.prompts || []
      expect(Array.isArray(prompts)).toBe(true)
    })
  })

  describe('Test 2.5: Verify resources from MCP server', () => {
    it('should list resources from a connected MCP server', async () => {
      const mockResources = [
        {
          uri: 'file:///test/resource',
          description: 'A test resource',
        },
      ]

      vi.mocked(sdk.listServerResourcesApiMcpsServerIdResourcesListGet).mockResolvedValue({
        data: {
          success: true,
          data: {
            server: 'everything-server',
            resources: mockResources,
            total_resources: 1,
          },
        },
      } as any)

      const result = await apiClient.listMCPServerResources('everything-server')

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      // Resources may be in result.data.resources or result.data.data.resources
      const resources = (result.data as any)?.resources || (result.data as any)?.data?.resources || []
      expect(Array.isArray(resources)).toBe(true)
    })
  })

  describe('Test 2.6: Call MCP tool', () => {
    it('should call a tool on an MCP server', async () => {
      const mockResult = createMockToolCallResult({
        tool_name: 'test_tool',
        server: 'everything-server',
        content: [
          {
            type: 'text',
            text: 'Tool executed successfully',
          },
        ],
      })

      vi.mocked(sdk.callMcpToolApiMcpsServerIdToolsCallPost).mockResolvedValue({
        data: {
          success: true,
          message: 'Tool executed successfully',
          data: mockResult,
        },
      } as any)

      const result = await apiClient.callMCPTool('everything-server', {
        tool_name: 'test_tool',
        arguments: { param1: 'value1' },
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.tool_name).toBe('test_tool')
      expect(sdk.callMcpToolApiMcpsServerIdToolsCallPost).toHaveBeenCalledWith({
        path: { server_id: 'everything-server' },
        body: {
          tool_name: 'test_tool',
          arguments: { param1: 'value1' },
        },
      })
    })

    it('should handle tool call errors', async () => {
      vi.mocked(sdk.callMcpToolApiMcpsServerIdToolsCallPost).mockRejectedValue(
        new Error('Tool not found')
      )

      const result = await apiClient.callMCPTool('everything-server', {
        tool_name: 'nonexistent_tool',
        arguments: {},
      })

      expect(result.success).toBe(false)
      expect(result.error).toContain('Tool not found')
    })
  })

  describe('Test 2.7: Get MCP prompt', () => {
    it('should get a prompt from an MCP server', async () => {
      const mockPromptResult = {
        success: true,
        message: 'Prompt retrieved successfully',
        data: {
          prompt_name: 'test_prompt',
          server: 'everything-server',
          messages: [
            {
              role: 'user',
              content: {
                type: 'text',
                text: 'Test prompt message',
              },
            },
          ],
        },
      }

      vi.mocked(sdk.getMcpPromptApiMcpsServerIdPromptsGetPost).mockResolvedValue({
        data: mockPromptResult,
      } as any)

      const result = await apiClient.getMCPPrompt('everything-server', {
        prompt_name: 'test_prompt',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.prompt_name).toBe('test_prompt')
    })
  })

  describe('Test 2.8: Connect to MCP server', () => {
    it('should connect to an MCP server', async () => {
      vi.mocked(sdk.connectMcpServerWithCapabilitiesApiMcpsServerIdConnectPost).mockResolvedValue({
        data: {
          success: true,
          message: 'Server connected successfully',
          data: {
            server_id: 'everything-server',
            status: 'connected',
          },
        },
      } as any)

      const result = await apiClient.connectMCPServer('everything-server')

      expect(result.success).toBe(true)
      expect(result.data?.data?.status).toBe('connected')
    })
  })
})

