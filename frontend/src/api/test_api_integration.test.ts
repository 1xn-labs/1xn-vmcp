/**
 * Test Suite 8: API Integration Tests
 * Tests API client integration, error handling, and edge cases
 * 
 * Similar to backend integration tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP } from '../test/test-setup'
import { createMockVMCP, createMockMCPServer } from '../test/api-mock-helpers'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  createVmcpApiVmcpsCreatePost: vi.fn(),
  getVmcpDetailsApiVmcpsVmcpIdGet: vi.fn(),
  updateVmcpApiVmcpsVmcpIdPut: vi.fn(),
  deleteVmcpApiVmcpsVmcpIdDelete: vi.fn(),
  listVmcpsApiVmcpsListGet: vi.fn(),
  installMcpServerApiMcpsInstallPost: vi.fn(),
  listMcpServersApiMcpsListGet: vi.fn(),
  connectMcpServerWithCapabilitiesApiMcpsServerIdConnectPost: vi.fn(),
  disconnectMcpServerApiMcpsServerIdDisconnectPost: vi.fn(),
  callVmcpToolApiVmcpsVmcpIdToolsCallPost: vi.fn(),
  getVmcpPromptApiVmcpsVmcpIdPromptsGetPost: vi.fn(),
  readVmcpResourceApiVmcpsVmcpIdResourcesReadPost: vi.fn(),
}))

describe('Test Suite 8: API Integration Tests', () => {
  let vmcpName: string
  let createdVMCP: ReturnType<typeof createTestVMCP>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    createdVMCP = createTestVMCP({ name: vmcpName })
    vi.clearAllMocks()
  })

  describe('API Error Handling', () => {
    it('should handle network errors gracefully', async () => {
      vi.mocked(sdk.createVmcpApiVmcpsCreatePost).mockRejectedValue(
        new Error('Network error: Failed to fetch')
      )

      const result = await apiClient.createVMCP({
        name: vmcpName,
        description: 'Test',
      })

      expect(result.success).toBe(false)
      expect(result.error).toContain('Network error')
    })

    it('should handle 404 errors', async () => {
      const error: any = new Error('Not found')
      error.status = 404
      vi.mocked(sdk.getVmcpDetailsApiVmcpsVmcpIdGet).mockRejectedValue(error)

      const result = await apiClient.getVMCPDetails('nonexistent-id')

      expect(result.success).toBe(false)
      expect(result.error).toBeDefined()
    })

    it('should handle 500 server errors', async () => {
      const error: any = new Error('Internal server error')
      error.status = 500
      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockRejectedValue(error)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        description: 'Updated',
      })

      expect(result.success).toBe(false)
      expect(result.error).toBeDefined()
    })
  })

  describe('Token Management', () => {
    it('should set and retrieve authentication token', async () => {
      // Import client module for mocking
      const clientModule = await import('./generated/client.gen')
      const { client } = clientModule
      
      // Mock getConfig to return the token
      vi.spyOn(client, 'getConfig').mockReturnValue({
        baseUrl: 'http://localhost:8000',
        headers: {
          Authorization: 'Bearer test-token-123',
        },
      } as any)

      const token = 'test-token-123'
      apiClient.setToken(token)
      const retrievedToken = apiClient.getToken()
      expect(retrievedToken).toBe(token)

      // Restore original
      vi.restoreAllMocks()
    })

    it('should handle undefined token', () => {
      apiClient.setToken(undefined)
      const token = apiClient.getToken()
      expect(token).toBeUndefined()
    })
  })

  describe('VMCP CRUD Operations', () => {
    it('should create, read, update, and delete a vMCP', async () => {
      // Create
      const mockVMCP = createMockVMCP({ name: vmcpName })
      vi.mocked(sdk.createVmcpApiVmcpsCreatePost).mockResolvedValue({
        data: { vMCP: mockVMCP },
      } as any)

      const createResult = await apiClient.createVMCP({
        name: vmcpName,
        description: 'Test vMCP',
      })
      expect(createResult.success).toBe(true)
      expect(createResult.data?.name).toBe(vmcpName)

      const vmcpId = mockVMCP.id

      // Read
      vi.mocked(sdk.getVmcpDetailsApiVmcpsVmcpIdGet).mockResolvedValue({
        data: mockVMCP,
      } as any)

      const readResult = await apiClient.getVMCPDetails(vmcpId)
      expect(readResult.success).toBe(true)
      expect(readResult.data?.id).toBe(vmcpId)

      // Update
      const updatedVMCP = { ...mockVMCP, description: 'Updated description' }
      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: { vMCP: updatedVMCP },
      } as any)

      const updateResult = await apiClient.updateVMCP(vmcpId, {
        description: 'Updated description',
      })
      expect(updateResult.success).toBe(true)
      expect(updateResult.data?.description).toBe('Updated description')

      // Delete
      vi.mocked(sdk.deleteVmcpApiVmcpsVmcpIdDelete).mockResolvedValue({
        data: { success: true },
      } as any)

      const deleteResult = await apiClient.deleteVMCP(vmcpId)
      expect(deleteResult.success).toBe(true)
    })
  })

  describe('MCP Server Operations', () => {
    it('should install and connect to an MCP server', async () => {
      const serverData = {
        name: 'test-server',
        url: 'http://localhost:8001/test/mcp',
        mode: 'http' as const,
        description: 'Test server',
      }

      const mockServer = createMockMCPServer(serverData)
      vi.mocked(sdk.installMcpServerApiMcpsInstallPost).mockResolvedValue({
        data: {
          success: true,
          message: 'Server installed',
          data: mockServer,
        },
      } as any)

      const installResult = await apiClient.installMCPServer(serverData)
      expect(installResult.success).toBe(true)

      // Connect
      vi.mocked(sdk.connectMcpServerWithCapabilitiesApiMcpsServerIdConnectPost).mockResolvedValue({
        data: {
          success: true,
          data: {
            server_id: mockServer.id,
            status: 'connected',
          },
        },
      } as any)

      const connectResult = await apiClient.connectMCPServer(mockServer.id)
      expect(connectResult.success).toBe(true)
    })
  })

  describe('Tool Execution', () => {
    it('should execute a vMCP tool and handle response', async () => {
      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'test_tool',
          result: { output: 'Tool executed successfully' },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'test_tool',
        arguments: { param: 'value' },
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.tool).toBe('test_tool')
    })
  })

  describe('Prompt and Resource Access', () => {
    it('should get a vMCP prompt', async () => {
      const mockPromptResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          prompt_id: '#test_prompt',
          messages: [
            {
              role: 'user',
              content: { type: 'text', text: 'Test prompt' },
            },
          ],
        },
      }

      vi.mocked(sdk.getVmcpPromptApiVmcpsVmcpIdPromptsGetPost).mockResolvedValue({
        data: mockPromptResult,
      } as any)

      const result = await apiClient.getVMCPPrompt(createdVMCP.id, {
        prompt_id: '#test_prompt',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.prompt_id).toBe('#test_prompt')
    })

    it('should read a vMCP resource', async () => {
      const mockResourceResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          uri: 'file:///test/resource',
          contents: [
            {
              uri: 'file:///test/resource',
              text: 'Resource content',
              mimeType: 'text/plain',
            },
          ],
        },
      }

      vi.mocked(sdk.readVmcpResourceApiVmcpsVmcpIdResourcesReadPost).mockResolvedValue({
        data: mockResourceResult,
      } as any)

      const result = await apiClient.getVMCPResource(createdVMCP.id, {
        uri: 'file:///test/resource',
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.uri).toBe('file:///test/resource')
    })
  })

  describe('Edge Cases', () => {
    it('should handle empty vMCP list', async () => {
      vi.mocked(sdk.listVmcpsApiVmcpsListGet).mockResolvedValue({
        data: { private: [], public: [] },
      } as any)

      const result = await apiClient.listVMCPS()
      expect(result.success).toBe(true)
      expect(result.data?.private).toEqual([])
      expect(result.data?.public).toEqual([])
    })

    it('should handle large response data', async () => {
      const largeVMCP = createMockVMCP({
        name: vmcpName,
        custom_tools: Array(100).fill(null).map((_, i) => ({
          tool_type: 'prompt',
          name: `tool_${i}`,
          description: `Tool ${i}`,
        })),
      })

      vi.mocked(sdk.getVmcpDetailsApiVmcpsVmcpIdGet).mockResolvedValue({
        data: largeVMCP,
      } as any)

      const result = await apiClient.getVMCPDetails(largeVMCP.id)
      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.length).toBe(100)
    })

    it('should handle concurrent requests', async () => {
      const mockVMCP = createMockVMCP({ name: vmcpName })
      vi.mocked(sdk.getVmcpDetailsApiVmcpsVmcpIdGet).mockResolvedValue({
        data: mockVMCP,
      } as any)

      const promises = Array(5)
        .fill(null)
        .map(() => apiClient.getVMCPDetails(mockVMCP.id))

      const results = await Promise.all(promises)
      results.forEach(result => {
        expect(result.success).toBe(true)
      })
    })
  })
})

