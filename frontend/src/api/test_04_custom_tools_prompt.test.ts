/**
 * Test Suite 4: Custom Tools (Prompt Type)
 * Tests prompt-type custom tools creation and execution
 * 
 * Corresponds to: backend/tests/test_04_custom_tools_prompt.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP } from '../test/test-setup'
import { createMockVMCP } from '../test/api-mock-helpers'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  createVmcpApiVmcpsCreatePost: vi.fn(),
  updateVmcpApiVmcpsVmcpIdPut: vi.fn(),
  listVmcpToolsApiVmcpsVmcpIdToolsListPost: vi.fn(),
  callVmcpToolApiVmcpsVmcpIdToolsCallPost: vi.fn(),
}))

describe('Test Suite 4: Custom Tools (Prompt Type)', () => {
  let vmcpName: string
  let createdVMCP: ReturnType<typeof createTestVMCP>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    createdVMCP = createTestVMCP({ name: vmcpName })
    vi.clearAllMocks()
  })

  describe('Test 4.1: Create simple prompt tool', () => {
    it('should create a prompt-type custom tool', async () => {
      const customTool = {
        tool_type: 'prompt',
        name: 'simple_prompt_tool',
        description: 'A simple prompt tool',
        variables: [],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [customTool],
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
      expect(result.data?.custom_tools).toBeDefined()
      expect(result.data?.custom_tools?.length).toBe(1)
      expect(result.data?.custom_tools?.[0].tool_type).toBe('prompt')
      expect(result.data?.custom_tools?.[0].name).toBe('simple_prompt_tool')
    })
  })

  describe('Test 4.2: List prompt tools', () => {
    it('should list prompt-type custom tools', async () => {
      const mockTools = [
        {
          name: 'prompt_tool_1',
          description: 'Prompt tool 1',
          inputSchema: { type: 'object', properties: {} },
        },
        {
          name: 'prompt_tool_2',
          description: 'Prompt tool 2',
          inputSchema: { type: 'object', properties: {} },
        },
      ]

      vi.mocked(sdk.listVmcpToolsApiVmcpsVmcpIdToolsListPost).mockResolvedValue({
        data: {
          success: true,
          data: {
            vmcp_id: createdVMCP.id,
            tools: mockTools,
            total_tools: 2,
          },
        },
      } as any)

      const result = await apiClient.listVMCPTools(createdVMCP.id)

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
    })
  })

  describe('Test 4.3: Call simple prompt tool', () => {
    it('should execute a prompt-type custom tool', async () => {
      const mockToolResult = {
        success: true,
        message: 'Tool executed successfully',
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'simple_prompt_tool',
          result: {
            messages: [
              {
                role: 'user',
                content: {
                  type: 'text',
                  text: 'Prompt tool executed',
                },
              },
            ],
          },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'simple_prompt_tool',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.tool).toBe('simple_prompt_tool')
    })
  })

  describe('Test 4.4: Create prompt tool with variables', () => {
    it('should create a prompt tool with input variables', async () => {
      const customTool = {
        tool_type: 'prompt',
        name: 'prompt_tool_with_vars',
        description: 'A prompt tool with variables',
        variables: [
          { name: 'message', description: 'Message to process', required: true },
          { name: 'format', description: 'Output format', required: false },
        ],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [customTool],
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
      const variables = (result.data?.custom_tools?.[0] as any)?.variables
      expect(Array.isArray(variables) ? variables.length : 0).toBe(2)
    })
  })

  describe('Test 4.5: Call prompt tool with variables', () => {
    it('should execute a prompt tool with variable substitution', async () => {
      const mockToolResult = {
        success: true,
        message: 'Tool executed successfully',
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'prompt_tool_with_vars',
          result: {
            messages: [
              {
                role: 'user',
                content: {
                  type: 'text',
                  text: 'Processed: Hello World in JSON format',
                },
              },
            ],
          },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'prompt_tool_with_vars',
        arguments: {
          message: 'Hello World',
          format: 'JSON',
        },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 4.6: Create prompt tool with config vars', () => {
    it('should create a prompt tool using environment variables', async () => {
      const customTool = {
        tool_type: 'prompt',
        name: 'prompt_tool_with_config',
        description: 'A prompt tool with config variables',
        variables: [],
        environment_variables: [
          { name: 'api_endpoint', value: 'https://api.example.com', description: 'API endpoint' },
        ],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [customTool],
        environment_variables: customTool.environment_variables,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
        environment_variables: customTool.environment_variables,
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 4.7: Prompt tool with MCP tool call', () => {
    it('should create a prompt tool that calls an MCP tool', async () => {
      const customTool = {
        tool_type: 'prompt',
        name: 'prompt_tool_with_mcp',
        description: 'A prompt tool that calls MCP tools',
        variables: [],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [customTool],
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

  describe('Test 4.8: Prompt tool with all features', () => {
    it('should create a prompt tool with all features combined', async () => {
      const complexTool = {
        tool_type: 'prompt',
        name: 'complex_prompt_tool',
        description: 'A complex prompt tool',
        variables: [
          { name: 'input', description: 'Input text', required: true },
        ],
        environment_variables: [
          { name: 'api_key', value: 'secret-key', description: 'API key' },
        ],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [complexTool],
        environment_variables: complexTool.environment_variables,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [complexTool],
        environment_variables: complexTool.environment_variables,
      })

      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.[0].name).toBe('complex_prompt_tool')
    })
  })
})

