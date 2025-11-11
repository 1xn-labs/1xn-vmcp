/**
 * Test Suite 3: Custom Prompts
 * Tests custom prompt creation and execution with variables, config vars, tool calls, etc.
 * 
 * Corresponds to: backend/tests/test_03_custom_prompts.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP, createTestHelpers } from '../test/test-setup'
import { createMockVMCP } from '../test/api-mock-helpers'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  createVmcpApiVmcpsCreatePost: vi.fn(),
  updateVmcpApiVmcpsVmcpIdPut: vi.fn(),
  getVmcpDetailsApiVmcpsVmcpIdGet: vi.fn(),
  listVmcpPromptsApiVmcpsVmcpIdPromptsListPost: vi.fn(),
  getVmcpPromptApiVmcpsVmcpIdPromptsGetPost: vi.fn(),
}))

describe('Test Suite 3: Custom Prompts', () => {
  let vmcpName: string
  let helpers: ReturnType<typeof createTestHelpers>
  let createdVMCP: ReturnType<typeof createTestVMCP>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    helpers = createTestHelpers()
    createdVMCP = createTestVMCP({ name: vmcpName })
    vi.clearAllMocks()
  })

  describe('Test 3.1: Create simple prompt', () => {
    it('should create a vMCP with a simple custom prompt', async () => {
      const customPrompt = {
        name: 'simple_prompt',
        text: 'This is a simple prompt',
        variables: [],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [customPrompt],
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_prompts: [customPrompt],
      })

      expect(result.success).toBe(true)
      expect(result.data?.custom_prompts).toBeDefined()
      expect(result.data?.custom_prompts?.length).toBe(1)
      expect(result.data?.custom_prompts?.[0].name).toBe('simple_prompt')
    })
  })

  describe('Test 3.2: List custom prompts', () => {
    it('should list custom prompts in a vMCP', async () => {
      const mockPrompts = [
        {
          name: 'prompt1',
          text: 'Prompt 1',
          variables: [],
        },
        {
          name: 'prompt2',
          text: 'Prompt 2',
          variables: [],
        },
      ]

      vi.mocked(sdk.listVmcpPromptsApiVmcpsVmcpIdPromptsListPost).mockResolvedValue({
        data: {
          success: true,
          data: {
            vmcp_id: createdVMCP.id,
            prompts: mockPrompts,
            total_prompts: 2,
          },
        },
      } as any)

      const result = await apiClient.listVMCPPrompts(createdVMCP.id)

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      if (Array.isArray(result.data)) {
        expect(result.data.length).toBeGreaterThanOrEqual(0)
      }
    })
  })

  describe('Test 3.3: Get custom prompt', () => {
    it('should get a custom prompt by ID', async () => {
      const mockPromptResult = {
        success: true,
        message: 'Prompt retrieved successfully',
        data: {
          vmcp_id: createdVMCP.id,
          prompt_id: '#simple_prompt',
          prompt: 'simple_prompt',
          messages: [
            {
              role: 'user',
              content: {
                type: 'text',
                text: 'This is a simple prompt',
              },
            },
          ],
        },
      }

      vi.mocked(sdk.getVmcpPromptApiVmcpsVmcpIdPromptsGetPost).mockResolvedValue({
        data: mockPromptResult,
      } as any)

      const result = await apiClient.getVMCPPrompt(createdVMCP.id, {
        prompt_id: '#simple_prompt',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.prompt_id).toBe('#simple_prompt')
    })
  })

  describe('Test 3.4: Create prompt with variables', () => {
    it('should create a prompt with variables', async () => {
      const customPrompt = {
        name: 'prompt_with_vars',
        text: 'Hello {{name}}, you are {{age}} years old',
        variables: [
          { name: 'name', description: 'Person name', required: true },
          { name: 'age', description: 'Person age', required: true },
        ],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [customPrompt],
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_prompts: [customPrompt],
      })

      expect(result.success).toBe(true)
      const variables = (result.data?.custom_prompts?.[0] as any)?.variables
      expect(Array.isArray(variables) ? variables.length : 0).toBe(2)
    })
  })

  describe('Test 3.5: Call prompt with variables', () => {
    it('should call a prompt with variable substitution', async () => {
      const mockPromptResult = {
        success: true,
        message: 'Prompt retrieved successfully',
        data: {
          vmcp_id: createdVMCP.id,
          prompt_id: '#prompt_with_vars',
          prompt: 'prompt_with_vars',
          messages: [
            {
              role: 'user',
              content: {
                type: 'text',
                text: 'Hello John, you are 30 years old',
              },
            },
          ],
        },
      }

      vi.mocked(sdk.getVmcpPromptApiVmcpsVmcpIdPromptsGetPost).mockResolvedValue({
        data: mockPromptResult,
      } as any)

      const result = await apiClient.getVMCPPrompt(createdVMCP.id, {
        prompt_id: '#prompt_with_vars',
        arguments: {
          name: 'John',
          age: '30',
        },
      })

      expect(result.success).toBe(true)
      expect(result.data?.data?.messages?.[0]?.content?.text).toContain('John')
      expect(result.data?.data?.messages?.[0]?.content?.text).toContain('30')
    })
  })

  describe('Test 3.6: Create prompt with config variables', () => {
    it('should create a prompt using environment variables', async () => {
      const customPrompt = {
        name: 'prompt_with_config',
        text: 'API Key: {{config.api_key}}',
        variables: [],
        environment_variables: [
          { name: 'api_key', value: 'secret-key-123', description: 'API key' },
        ],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [customPrompt],
        environment_variables: customPrompt.environment_variables,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_prompts: [customPrompt],
        environment_variables: customPrompt.environment_variables,
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 3.7: Create prompt with tool call', () => {
    it('should create a prompt that triggers a tool call', async () => {
      const customPrompt = {
        name: 'prompt_with_tool',
        text: 'Execute a tool',
        variables: [],
        tool_calls: [
          {
            name: 'test_tool',
            arguments: { param: 'value' },
          },
        ],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [customPrompt],
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_prompts: [customPrompt],
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 3.8: Create prompt with prompt reference', () => {
    it('should create a prompt that references another prompt', async () => {
      const prompt1 = {
        name: 'base_prompt',
        text: 'Base prompt text',
        variables: [],
      }

      const prompt2 = {
        name: 'extended_prompt',
        text: '{{#base_prompt}} Extended text',
        variables: [],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [prompt1, prompt2],
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_prompts: [prompt1, prompt2],
      })

      expect(result.success).toBe(true)
      expect(result.data?.custom_prompts?.length).toBe(2)
    })
  })

  describe('Test 3.9: Create prompt with resource', () => {
    it('should create a prompt that references a resource', async () => {
      const customPrompt = {
        name: 'prompt_with_resource',
        text: 'Read resource: {{resource.file:///test.txt}}',
        variables: [],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [customPrompt],
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_prompts: [customPrompt],
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 3.10: Create complex prompt', () => {
    it('should create a prompt with all features combined', async () => {
      const complexPrompt = {
        name: 'complex_prompt',
        text: 'Hello {{name}}, use API key {{config.api_key}} and execute {{tool.test_tool}}',
        variables: [
          { name: 'name', description: 'Name', required: true },
        ],
        environment_variables: [
          { name: 'api_key', value: 'secret', description: 'API key' },
        ],
        tool_calls: [
          {
            name: 'test_tool',
            arguments: { param: 'value' },
          },
        ],
      }

      const updatedVMCP = createMockVMCP({
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [complexPrompt],
        environment_variables: complexPrompt.environment_variables,
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP(createdVMCP.id, {
        custom_prompts: [complexPrompt],
        environment_variables: complexPrompt.environment_variables,
      })

      expect(result.success).toBe(true)
      expect(result.data?.custom_prompts?.[0].name).toBe('complex_prompt')
    })
  })
})

