/**
 * Test Suite 5: Custom Tools (Python Type)
 * Tests Python-type custom tools with various parameter types and error handling
 * 
 * Corresponds to: backend/tests/test_05_custom_tools_python.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP } from '../test/test-setup'
import { createMockVMCP } from '../test/api-mock-helpers'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  updateVmcpApiVmcpsVmcpIdPut: vi.fn(),
  callVmcpToolApiVmcpsVmcpIdToolsCallPost: vi.fn(),
  listVmcpToolsApiVmcpsVmcpIdToolsListPost: vi.fn(),
}))

describe('Test Suite 5: Custom Tools (Python Type)', () => {
  let vmcpName: string
  let createdVMCP: ReturnType<typeof createTestVMCP>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    createdVMCP = createTestVMCP({ name: vmcpName })
    vi.clearAllMocks()
  })

  describe('Test 5.1: Create simple Python tool', () => {
    it('should create a Python-type custom tool', async () => {
      const customTool = {
        tool_type: 'python',
        name: 'simple_python_tool',
        description: 'A simple Python tool',
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
      expect(result.data?.custom_tools?.[0].tool_type).toBe('python')
    })
  })

  describe('Test 5.2: Call simple Python tool', () => {
    it('should execute a Python tool', async () => {
      const mockToolResult = {
        success: true,
        message: 'Tool executed successfully',
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'simple_python_tool',
          result: {
            output: 'Python tool executed successfully',
          },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'simple_python_tool',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.tool).toBe('simple_python_tool')
    })
  })

  describe('Test 5.3: Python tool with string type', () => {
    it('should create and call a Python tool with string parameter', async () => {
      const customTool = {
        tool_type: 'python',
        name: 'python_string_tool',
        description: 'Python tool with string parameter',
        variables: [
          { name: 'text', description: 'Text input', required: true, type: 'string' },
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

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'python_string_tool',
          result: { output: 'Processed: Hello World' },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'python_string_tool',
        arguments: { text: 'Hello World' },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 5.4: Python tool with list type', () => {
    it('should handle Python tool with list parameter', async () => {
      const customTool = {
        tool_type: 'python',
        name: 'python_list_tool',
        description: 'Python tool with list parameter',
        variables: [
          { name: 'items', description: 'List of items', required: true, type: 'list' },
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

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'python_list_tool',
          result: { output: 'Processed 3 items' },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'python_list_tool',
        arguments: { items: ['item1', 'item2', 'item3'] },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 5.5: Python tool with dict type', () => {
    it('should handle Python tool with dictionary parameter', async () => {
      const customTool = {
        tool_type: 'python',
        name: 'python_dict_tool',
        description: 'Python tool with dict parameter',
        variables: [
          { name: 'data', description: 'Data dictionary', required: true, type: 'dict' },
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

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'python_dict_tool',
          result: { output: 'Processed dictionary' },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'python_dict_tool',
        arguments: { data: { key: 'value', nested: { foo: 'bar' } } },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 5.6: Python tool with float type', () => {
    it('should handle Python tool with float parameter', async () => {
      const customTool = {
        tool_type: 'python',
        name: 'python_float_tool',
        description: 'Python tool with float parameter',
        variables: [
          { name: 'number', description: 'Float number', required: true, type: 'float' },
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

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'python_float_tool',
          result: { output: 'Processed: 3.14159' },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'python_float_tool',
        arguments: { number: 3.14159 },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 5.7: Python tool with default values', () => {
    it('should handle Python tool with default parameter values', async () => {
      const customTool = {
        tool_type: 'python',
        name: 'python_default_tool',
        description: 'Python tool with default values',
        variables: [
          { name: 'param1', description: 'Parameter 1', required: true, type: 'string' },
          { name: 'param2', description: 'Parameter 2', required: false, type: 'string', default_value: 'default' },
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
    })
  })

  describe('Test 5.8: Python tool complex logic', () => {
    it('should handle Python tool with complex logic', async () => {
      const customTool = {
        tool_type: 'python',
        name: 'python_complex_tool',
        description: 'Python tool with complex logic',
        variables: [
          { name: 'input_data', description: 'Input data', required: true, type: 'dict' },
          { name: 'operation', description: 'Operation type', required: true, type: 'string' },
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

      await apiClient.updateVMCP(createdVMCP.id, {
        custom_tools: [customTool],
      })

      const mockToolResult = {
        success: true,
        data: {
          vmcp_id: createdVMCP.id,
          tool: 'python_complex_tool',
          result: { output: 'Complex operation completed' },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'python_complex_tool',
        arguments: {
          input_data: { key: 'value' },
          operation: 'process',
        },
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 5.9: Python tool error handling', () => {
    it('should handle Python tool execution errors', async () => {
      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockRejectedValue(
        new Error('Python execution error: division by zero')
      )

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'python_error_tool',
        arguments: { value: 0 },
      })

      expect(result.success).toBe(false)
      expect(result.error).toContain('error')
    })
  })
})

