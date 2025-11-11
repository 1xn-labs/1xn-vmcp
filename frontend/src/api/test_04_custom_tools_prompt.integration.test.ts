/**
 * Integration Test Suite 4: Custom Tools - Prompt Type
 * Tests for prompt-based custom tools with REAL API calls
 * 
 * Requires: Backend server running on localhost:8000
 * 
 * Corresponds to: backend/tests/test_04_custom_tools_prompt.py
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

setupIntegrationTests()

describe('Integration Test Suite 4: Custom Tools - Prompt Type', () => {
  let createdVMCP: Awaited<ReturnType<typeof createVMCPForTest>>

  beforeAll(async () => {
    await requireBackend()
    createdVMCP = await createVMCPForTest(generateVMCPName())
  })

  describe('Test 4.1: Create a simple prompt tool', () => {
    it('should create a simple prompt tool', async () => {
      console.log(`\n📦 Test 4.1 - Creating simple prompt tool: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'simple_analyzer',
            description: 'A simple analysis tool',
            text: 'Analyze the provided data and give insights',
            tool_type: 'prompt',
            variables: [],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.length).toBe(1)
      expect(result.data?.custom_tools?.[0]?.name).toBe('simple_analyzer')
      expect(result.data?.custom_tools?.[0]?.tool_type).toBe('prompt')

      console.log('✅ Simple prompt tool created successfully')
    })
  })

  describe('Test 4.2: List prompt tools via API', () => {
    it('should list prompt tools', async () => {
      console.log(`\n📦 Test 4.2 - Listing prompt tools via API: ${createdVMCP.id}`)

      // Get full vMCP config first (like Python tests do)
      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      // Modify the full config by adding a custom tool
      const updatedConfig: any = {
        id: vmcpData.data.id,
        name: vmcpData.data.name,
        description: vmcpData.data.description,
        system_prompt: vmcpData.data.system_prompt,
        custom_tools: [
          ...(vmcpData.data.custom_tools || []),
          {
            name: 'data_formatter',
            description: 'Format data tool',
            text: 'Format the data in a readable way',
            tool_type: 'prompt',
            variables: [],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const toolsResult = await apiClient.listVMCPTools(createdVMCP.id)
      expect(toolsResult.success).toBe(true)
      const tools = toolsResult.data?.tools || toolsResult.data?.data?.tools || []
      expect(tools.some((t: any) => t.name === 'data_formatter')).toBe(true)

      console.log('✅ Prompt tool listed successfully')
    })
  })

  describe('Test 4.3: Call a simple prompt tool', () => {
    it('should call a simple prompt tool', async () => {
      console.log(`\n📦 Test 4.3 - Calling simple prompt tool: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'echo_tool',
            description: 'Echo tool',
            text: 'Echo: This is a test message',
            tool_type: 'prompt',
            variables: [],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'echo_tool',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()

      console.log('✅ Prompt tool call successful')
    })
  })

  describe('Test 4.4: Create prompt tool with variables', () => {
    it('should create prompt tool with variables', async () => {
      console.log(`\n📦 Test 4.4 - Creating prompt tool with variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'personalized_report',
            description: 'Generate personalized report',
            text: 'Generate a @param.report_type report for @param.user_name',
            tool_type: 'prompt',
            variables: [
              { name: 'report_type', description: 'Type of report', required: true },
              { name: 'user_name', description: "User's name", required: true },
            ],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const variables = result.data?.custom_tools?.[0]?.variables
      expect(Array.isArray(variables) ? variables.length : 0).toBe(2)

      console.log('✅ Prompt tool with variables created successfully')
    })
  })

  describe('Test 4.5: Call prompt tool with variable substitution', () => {
    it('should call prompt tool with variables', async () => {
      console.log(`\n📦 Test 4.5 - Calling prompt tool with variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'greeting_tool',
            description: 'Greeting tool',
            text: 'Hello @param.name, your role is @param.role!',
            tool_type: 'prompt',
            variables: [
              { name: 'name', description: "User's name", required: true },
              { name: 'role', description: "User's role", required: true },
            ],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'greeting_tool',
        arguments: { name: 'Bob', role: 'Developer' },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        const text = result.data.content[0].text
        expect(text).toContain('Bob')
        expect(text).toContain('Developer')
      }

      console.log('✅ Prompt tool with variable substitution successful')
    })
  })

  describe('Test 4.6: Create prompt tool with @config variables', () => {
    it('should create prompt tool with config variables', async () => {
      console.log(`\n📦 Test 4.6 - Creating prompt tool with config variables: ${createdVMCP.id}`)

      // Add environment variables
      await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'company_name', value: 'TechCorp' },
        { name: 'support_email', value: 'support@techcorp.com' },
      ])

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'contact_info_tool',
            description: 'Provide contact information',
            text: 'Contact @config.company_name at @config.support_email',
            tool_type: 'prompt',
            variables: [],
            environment_variables: ['company_name', 'support_email'],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const envVars = result.data?.custom_tools?.[0]?.environment_variables
      expect(Array.isArray(envVars) ? envVars.length : 0).toBe(2)

      console.log('✅ Prompt tool with config variables created successfully')
    })
  })

  describe('Test 4.7: Call prompt tool with config variable substitution', () => {
    it('should call prompt tool with config variables', async () => {
      console.log(`\n📦 Test 4.7 - Calling prompt tool with config variables: ${createdVMCP.id}`)

      // Add environment variables
      await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'api_version', value: 'v2.0' },
        { name: 'base_endpoint', value: 'https://api.test.com' },
      ])

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'api_info_tool',
            description: 'API information tool',
            text: 'API: @config.base_endpoint version @config.api_version',
            tool_type: 'prompt',
            variables: [],
            environment_variables: ['api_version', 'base_endpoint'],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'api_info_tool',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        const text = result.data.content[0].text
        expect(text).toContain('v2.0')
        expect(text).toContain('https://api.test.com')
      }

      console.log('✅ Prompt tool with config variable substitution successful')
    })
  })

  describe('Test 4.8: Prompt tool with MCP tool call', () => {
    it('should create prompt tool that calls MCP server tool', async () => {
      console.log(`\n📦 Test 4.8 - Prompt tool with MCP tool call: ${createdVMCP.id}`)

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

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'weather_reporter',
            description: 'Report weather tool',
            text: "Weather report: @tool.get_weather(city='Paris')",
            tool_type: 'prompt',
            variables: [],
            environment_variables: [],
            tool_calls: [{ tool: 'get_weather', arguments: { city: 'Paris' } }],
            atomic_blocks: [],
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'weather_reporter',
        arguments: {},
      })

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()

      console.log('✅ Prompt tool with MCP tool call successful')
    })
  })

  describe('Test 4.9: Prompt tool with all features', () => {
    it('should create prompt tool with all features combined', async () => {
      console.log(`\n📦 Test 4.9 - Prompt tool with all features: ${createdVMCP.id}`)

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

      // Add environment variables
      await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'default_city', value: 'Tokyo' },
      ])

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'comprehensive_reporter',
            description: 'Comprehensive reporting tool',
            text: `Generate Report:
User: @param.user_name
Default City: @config.default_city
Weather Data: @tool.get_weather(city=@param.city)
Summary: @param.summary`,
            tool_type: 'prompt',
            variables: [
              { name: 'user_name', description: "User's name", required: true },
              { name: 'city', description: 'City for weather', required: false },
              { name: 'summary', description: 'Summary text', required: false },
            ],
            environment_variables: ['default_city'],
            tool_calls: [{ tool: 'get_weather', arguments: { city: '@param.city' } }],
            atomic_blocks: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const tool = result.data?.custom_tools?.[0]
      const variables = tool?.variables
      const envVars = tool?.environment_variables
      const toolCalls = tool?.tool_calls
      expect(Array.isArray(variables) ? variables.length : 0).toBe(3)
      expect(Array.isArray(envVars) ? envVars.length : 0).toBe(1)
      expect(Array.isArray(toolCalls) ? toolCalls.length : 0).toBe(1)

      console.log('✅ Comprehensive prompt tool created successfully')
    })
  })
})

