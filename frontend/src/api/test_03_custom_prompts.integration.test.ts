/**
 * Integration Test Suite 3: Custom Prompts
 * Tests custom prompts with variables, tool calls, resources, and system variables with REAL API calls
 * 
 * Requires: Backend server running on localhost:8000
 * 
 * Corresponds to: backend/tests/test_03_custom_prompts.py
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

describe('Integration Test Suite 3: Custom Prompts', () => {
  let createdVMCP: Awaited<ReturnType<typeof createVMCPForTest>>

  beforeAll(async () => {
    await requireBackend()
    createdVMCP = await createVMCPForTest(generateVMCPName())
  })

  describe('Test 3.1: Create a simple custom prompt', () => {
    it('should create a simple prompt without variables', async () => {
      console.log(`\n📦 Test 3.1 - Creating simple custom prompt: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'simple_greeting',
            description: 'A simple greeting prompt',
            text: 'Say hello to the user in a friendly manner',
            variables: [],
            environment_variables: [],
            tool_calls: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_prompts?.length).toBe(1)
      expect(result.data?.custom_prompts?.[0]?.name).toBe('simple_greeting')

      console.log('✅ Simple prompt created successfully')
    })
  })

  describe('Test 3.2: List custom prompts via API', () => {
    it('should list custom prompts', async () => {
      console.log(`\n📦 Test 3.2 - Listing custom prompts via API: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'test_prompt',
            description: 'Test prompt',
            text: 'This is a test prompt',
            variables: [],
            environment_variables: [],
            tool_calls: [],
          },
        ],
      }

      const updateResult = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(updateResult.success).toBe(true)
      await wait(200)

      const result = await apiClient.getVMCPDetails(createdVMCP.id)
      expect(result.success).toBe(true)
      expect(result.data?.custom_prompts?.some((p: any) => p.name === 'test_prompt')).toBe(true)

      console.log('✅ Custom prompt listed successfully')
    })
  })

  describe('Test 3.3: Get a custom prompt via API', () => {
    it('should get a custom prompt', async () => {
      console.log(`\n📦 Test 3.3 - Getting custom prompt via API: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'get_test_prompt',
            description: 'Prompt for testing get operation',
            text: 'Please analyze the following data carefully',
            variables: [],
            environment_variables: [],
            tool_calls: [],
          },
        ],
      }

      const updateResult = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(updateResult.success).toBe(true)
      await wait(200)

      const promptResult = await apiClient.getVMCPPrompt(createdVMCP.id, {
        prompt_id: '#get_test_prompt',
        arguments: {},
      })

      expect(promptResult.success).toBe(true)
      expect(promptResult.data).toBeDefined()

      console.log('✅ Custom prompt retrieved successfully')
    })
  })

  describe('Test 3.4: Create prompt with @param variables', () => {
    it('should create prompt with variables', async () => {
      console.log(`\n📦 Test 3.4 - Creating prompt with variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'greet_in_language',
            description: 'Greet user in specific language',
            text: 'Greet the user @param.name in @param.language language',
            variables: [
              { name: 'name', description: "User's name", required: true },
              { name: 'language', description: 'Language for greeting', required: true },
            ],
            environment_variables: [],
            tool_calls: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const variables = result.data?.custom_prompts?.[0]?.variables
      expect(Array.isArray(variables) ? variables.length : 0).toBe(2)

      console.log('✅ Prompt with variables created successfully')
    })
  })

  describe('Test 3.5: Call prompt with variable substitution', () => {
    it('should call prompt with variables', async () => {
      console.log(`\n📦 Test 3.5 - Calling prompt with variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'personalized_greeting',
            description: 'Personalized greeting',
            text: 'Hello @param.name, welcome to @param.location!',
            variables: [
              { name: 'name', description: "User's name", required: true },
              { name: 'location', description: 'Location', required: true },
            ],
            environment_variables: [],
            tool_calls: [],
          },
        ],
      }

      const updateResult = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(updateResult.success).toBe(true)
      await wait(200)

      const promptResult = await apiClient.getVMCPPrompt(createdVMCP.id, {
        prompt_id: '#personalized_greeting',
        arguments: { name: 'Alice', location: 'Wonderland' },
      })

      expect(promptResult.success).toBe(true)
      if (promptResult.data?.messages?.[0]?.content?.text) {
        const text = promptResult.data.messages[0].content.text
        expect(text).toContain('Alice')
        expect(text).toContain('Wonderland')
      }

      console.log('✅ Prompt with variable substitution successful')
    })
  })

  describe('Test 3.6: Create prompt with @config variables', () => {
    it('should create prompt with config variables', async () => {
      console.log(`\n📦 Test 3.6 - Creating prompt with config variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      // Save environment variables first
      const envResult = await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'api_key', value: 'test-api-key-123' },
        { name: 'base_url', value: 'https://api.example.com' },
      ])
      expect(envResult.success).toBe(true)

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'api_request_prompt',
            description: 'Prompt using API configuration',
            text: 'Make a request to @config.base_url using API key @config.api_key',
            variables: [],
            environment_variables: ['api_key', 'base_url'],
            tool_calls: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const envVars = result.data?.custom_prompts?.[0]?.environment_variables
      expect(Array.isArray(envVars) ? envVars.length : 0).toBe(2)

      console.log('✅ Prompt with config variables created successfully')
    })
  })

  describe('Test 3.7: Call prompt with config variable substitution', () => {
    it('should call prompt with config variables', async () => {
      console.log(`\n📦 Test 3.7 - Calling prompt with config variables: ${createdVMCP.id}`)

      // Save environment variables
      const envResult = await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'service_name', value: 'TestService' },
        { name: 'version', value: '1.0.0' },
      ])
      expect(envResult.success).toBe(true)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'system_info_prompt',
            description: 'System info prompt',
            text: 'Connect to @config.service_name version @config.version',
            variables: [],
            environment_variables: ['service_name', 'version'],
            tool_calls: [],
          },
        ],
      }

      const updateResult = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(updateResult.success).toBe(true)
      await wait(200)

      const promptResult = await apiClient.getVMCPPrompt(createdVMCP.id, {
        prompt_id: '#system_info_prompt',
        arguments: {},
      })

      expect(promptResult.success).toBe(true)
      if (promptResult.data?.messages?.[0]?.content?.text) {
        const text = promptResult.data.messages[0].content.text
        expect(text).toContain('TestService')
        expect(text).toContain('1.0.0')
      }

      console.log('✅ Prompt with config variable substitution successful')
    })
  })

  describe('Test 3.8: Create prompt with @tool call', () => {
    it('should create prompt with tool call', async () => {
      console.log(`\n📦 Test 3.8 - Creating prompt with tool call: ${createdVMCP.id}`)

      // Install MCP server
      const serverId = await createMCPServerForTest({
        name: `test-server-${Date.now()}`,
        url: MCP_SERVERS.allfeature,
        mode: 'http',
      })

      // Add server to vMCP
      const addResult = await apiClient.addServerToVMCP(createdVMCP.id, {
        server_id: serverId,
      })
      expect(addResult.success).toBe(true)
      await wait(500)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'weather_analysis_prompt',
            description: 'Analyze weather data',
            text: "Get the current weather: @tool.get_weather(city='London') and analyze it",
            variables: [],
            environment_variables: [],
            tool_calls: [{ tool: 'get_weather', arguments: { city: 'London' } }],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const toolCalls = result.data?.custom_prompts?.[0]?.tool_calls
      expect(Array.isArray(toolCalls) ? toolCalls.length : 0).toBe(1)

      console.log('✅ Prompt with tool call created successfully')
    })
  })

  describe('Test 3.9: Create prompt with prompt reference', () => {
    it('should create prompt that references another prompt', async () => {
      console.log(`\n📦 Test 3.9 - Creating prompt with prompt reference: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'base_greeting',
            description: 'Base greeting',
            text: 'Hello, welcome!',
            variables: [],
            environment_variables: [],
            tool_calls: [],
          },
          {
            name: 'extended_greeting',
            description: 'Extended greeting with base',
            text: '@prompt.base_greeting Now let me help you with your questions.',
            variables: [],
            environment_variables: [],
            tool_calls: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const extendedPrompt = result.data?.custom_prompts?.find((p: any) => p.name === 'extended_greeting')
      expect(extendedPrompt?.text).toContain('@prompt.base_greeting')

      console.log('✅ Prompt with prompt reference created successfully')
    })
  })

  describe('Test 3.10: Create prompt with @resource reference', () => {
    it('should create prompt with resource reference', async () => {
      console.log(`\n📦 Test 3.10 - Creating prompt with resource reference: ${createdVMCP.id}`)

      // Install MCP server
      const serverId = await createMCPServerForTest({
        name: `test-server-${Date.now()}`,
        url: MCP_SERVERS.everything,
        mode: 'http',
      })

      const addResult = await apiClient.addServerToVMCP(createdVMCP.id, {
        server_id: serverId,
      })
      expect(addResult.success).toBe(true)
      await wait(500)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'dashboard_analysis_prompt',
            description: 'Analyze dashboard data',
            text: 'Analyze the following dashboard data: @resource.everything://dashboard',
            variables: [],
            environment_variables: [],
            tool_calls: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_prompts?.[0]?.text).toContain('@resource.everything://dashboard')

      console.log('✅ Prompt with resource reference created successfully')
    })
  })

  describe('Test 3.11: Create complex prompt with all features', () => {
    it('should create prompt with all features combined', async () => {
      console.log(`\n📦 Test 3.11 - Creating complex prompt with all features: ${createdVMCP.id}`)

      // Install MCP server
      const serverId = await createMCPServerForTest({
        name: `test-server-${Date.now()}`,
        url: MCP_SERVERS.allfeature,
        mode: 'http',
      })

      const addResult = await apiClient.addServerToVMCP(createdVMCP.id, {
        server_id: serverId,
      })
      expect(addResult.success).toBe(true)
      await wait(500)

      // Save environment variables
      const envResult = await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'default_city', value: 'London' },
      ])
      expect(envResult.success).toBe(true)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_prompts: [
          {
            name: 'comprehensive_analysis',
            description: 'Comprehensive analysis with all features',
            text: `Analyze the following:
User: @param.user_name
City: @config.default_city
Weather: @tool.get_weather(city=@param.city)
Additional Info: @param.details`,
            variables: [
              { name: 'user_name', description: "User's name", required: true },
              { name: 'city', description: 'City name', required: false },
              { name: 'details', description: 'Additional details', required: false },
            ],
            environment_variables: ['default_city'],
            tool_calls: [{ tool: 'get_weather', arguments: { city: '@param.city' } }],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const prompt = result.data?.custom_prompts?.[0]
      const variables = prompt?.variables
      const envVars = prompt?.environment_variables
      const toolCalls = prompt?.tool_calls
      expect(Array.isArray(variables) ? variables.length : 0).toBe(3)
      expect(Array.isArray(envVars) ? envVars.length : 0).toBe(1)
      expect(Array.isArray(toolCalls) ? toolCalls.length : 0).toBe(1)

      console.log('✅ Complex prompt with all features created successfully')
    })
  })
})

