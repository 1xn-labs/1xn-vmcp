/**
 * Test Suite 6: Custom Tools (HTTP Type)
 * Tests HTTP-type custom tools with different methods, auth, query params, etc.
 * 
 * Corresponds to: backend/tests/test_06_custom_tools_http.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP } from '../test/test-setup'
import { createMockVMCP } from '../test/api-mock-helpers'
import { TEST_HTTP_SERVER } from '../test/test-setup'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  updateVmcpApiVmcpsVmcpIdPut: vi.fn(),
  callVmcpToolApiVmcpsVmcpIdToolsCallPost: vi.fn(),
}))

describe('Test Suite 6: Custom Tools (HTTP Type)', () => {
  let vmcpName: string
  let createdVMCP: ReturnType<typeof createTestVMCP>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    createdVMCP = createTestVMCP({ name: vmcpName })
    vi.clearAllMocks()
  })

  describe('Test 6.1: Create simple HTTP GET tool', () => {
    it('should create an HTTP GET tool', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_get_tool',
        description: 'A simple HTTP GET tool',
        variables: [],
        url: `${TEST_HTTP_SERVER}/api/data`,
        method: 'GET',
      }

      const { system_prompt, environment_variables, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.[0].tool_type).toBe('http')
    })
  })

  describe('Test 6.2: Call HTTP GET tool', () => {
    it('should execute an HTTP GET tool', async () => {
      const mockToolResult = {
        success: true,
        message: 'Tool executed successfully',
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'http_get_tool',
          result: {
            status_code: 200,
            response: { data: 'GET response data' },
          },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'http_get_tool',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.result?.status_code).toBe(200)
    })
  })

  describe('Test 6.3: HTTP tool with API key header', () => {
    it('should create and call HTTP tool with API key authentication', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_api_key_tool',
        description: 'HTTP tool with API key',
        variables: [],
        url: `${TEST_HTTP_SERVER}/api/secure`,
        method: 'GET',
        headers: {
          'X-API-Key': '{{config.api_key}}',
        },
      }

      const { system_prompt, environment_variables: _, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        environment_variables: [
          { name: 'api_key', value: 'secret-api-key', description: 'API key' },
        ],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
        environment_variables: updatedVMCP.environment_variables,
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'http_api_key_tool',
          result: { status_code: 200, response: { authenticated: true } },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'http_api_key_tool',
        arguments: {},
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 6.4: HTTP tool with bearer token', () => {
    it('should handle HTTP tool with bearer token authentication', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_bearer_tool',
        description: 'HTTP tool with bearer token',
        variables: [],
        url: `${TEST_HTTP_SERVER}/api/auth`,
        method: 'GET',
        headers: {
          Authorization: 'Bearer {{config.token}}',
        },
      }

      const { system_prompt, environment_variables, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 6.5: HTTP tool with basic auth', () => {
    it('should handle HTTP tool with basic authentication', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_basic_auth_tool',
        description: 'HTTP tool with basic auth',
        variables: [],
        url: `${TEST_HTTP_SERVER}/api/basic-auth`,
        method: 'GET',
        auth: {
          type: 'basic',
          username: '{{config.username}}',
          password: '{{config.password}}',
        },
      }

      const { system_prompt, environment_variables, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 6.6: HTTP tool with query params', () => {
    it('should handle HTTP tool with query parameters', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_query_tool',
        description: 'HTTP tool with query params',
        variables: [
          { name: 'query', description: 'Search query', required: true },
          { name: 'limit', description: 'Result limit', required: false },
        ],
        url: `${TEST_HTTP_SERVER}/api/search?q={{query}}&limit={{limit}}`,
        method: 'GET',
      }

      const { system_prompt, environment_variables, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'http_query_tool',
          result: { status_code: 200, response: { results: [] } },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'http_query_tool',
        arguments: { query: 'test', limit: '10' },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 6.7: HTTP tool with param substitution', () => {
    it('should handle HTTP tool with parameter substitution in URL', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_param_sub_tool',
        description: 'HTTP tool with param substitution',
        variables: [
          { name: 'id', description: 'Resource ID', required: true },
        ],
        url: `${TEST_HTTP_SERVER}/api/resources/{{id}}`,
        method: 'GET',
      }

      const { system_prompt, environment_variables, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'http_param_sub_tool',
          result: { status_code: 200, response: { id: '123' } },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'http_param_sub_tool',
        arguments: { id: '123' },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 6.8: HTTP tool with config substitution', () => {
    it('should handle HTTP tool with config variable substitution', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_config_sub_tool',
        description: 'HTTP tool with config substitution',
        variables: [],
        url: '{{config.base_url}}/api/data',
        method: 'GET',
      }

      const { system_prompt, environment_variables: _, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        environment_variables: [
          { name: 'base_url', value: TEST_HTTP_SERVER, description: 'Base URL' },
        ],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
        environment_variables: updatedVMCP.environment_variables,
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 6.9: HTTP POST with JSON body', () => {
    it('should handle HTTP POST tool with JSON body', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_post_tool',
        description: 'HTTP POST tool with JSON body',
        variables: [
          { name: 'data', description: 'Request data', required: true },
        ],
        url: `${TEST_HTTP_SERVER}/api/create`,
        method: 'POST',
        body: '{{data}}',
      }

      const { system_prompt, environment_variables, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'http_post_tool',
          result: { status_code: 201, response: { created: true } },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'http_post_tool',
        arguments: { data: { name: 'test', value: '123' } },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 6.10: HTTP PATCH method', () => {
    it('should handle HTTP PATCH tool', async () => {
      const customTool = {
        tool_type: 'http',
        name: 'http_patch_tool',
        description: 'HTTP PATCH tool',
        variables: [
          { name: 'updates', description: 'Update data', required: true },
        ],
        url: `${TEST_HTTP_SERVER}/api/update`,
        method: 'PATCH',
        body: '{{updates}}',
      }

      const { system_prompt, environment_variables, ...restCreatedVMCP } = createdVMCP as any
      const updatedVMCP = createMockVMCP({
        ...restCreatedVMCP,
        custom_tools: [customTool],
        system_prompt: system_prompt ?? null,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'http_patch_tool',
          result: { status_code: 200, response: { updated: true } },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'http_patch_tool',
        arguments: { updates: { field: 'new_value' } },
      })

      expect(result.success).toBe(true)
    })
  })
})

