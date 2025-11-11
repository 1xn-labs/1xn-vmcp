/**
 * Integration Test Suite 7: Import Collection
 * Tests for importing Postman collections and OpenAPI specs as tools with REAL API calls
 * 
 * Requires: 
 * - Backend server running on localhost:8000
 * - Test HTTP server running on localhost:8002
 * 
 * Corresponds to: backend/tests/test_07_import_collection.py
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { apiClient } from './client'
import {
  setupIntegrationTests,
  requireBackend,
  createVMCPForTest,
  wait,
} from '../test/integration-setup'
import { generateVMCPName, TEST_HTTP_SERVER } from '../test/test-setup'

setupIntegrationTests()

describe('Integration Test Suite 7: Import Collection', () => {
  let createdVMCP: Awaited<ReturnType<typeof createVMCPForTest>>

  beforeAll(async () => {
    await requireBackend()
    createdVMCP = await createVMCPForTest(generateVMCPName())
  })

  describe('Test 7.1: Create tool mimicking imported collection', () => {
    it('should create a tool similar to what would be imported from Postman', async () => {
      console.log(`\n📦 Test 7.1 - Creating tool mimicking collection: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'health_check',
            description: 'Health check endpoint from collection',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/health`,
              headers: {},
              query_params: {},
              auth: { type: 'none' },
            },
            variables: [],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
            source: 'postman_collection',
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.length).toBe(1)
      expect(result.data?.custom_tools?.[0]?.source).toBe('postman_collection')

      console.log('✅ Tool mimicking collection created successfully')
    })
  })

  describe('Test 7.2: List imported collection tools', () => {
    it('should list tools imported from collection', async () => {
      console.log(`\n📦 Test 7.2 - Listing imported collection tools: ${createdVMCP.id}`)

      // Get full vMCP config first (like Python tests do)
      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig: any = {
        id: vmcpData.data.id,
        name: vmcpData.data.name,
        description: vmcpData.data.description,
        system_prompt: vmcpData.data.system_prompt,
        custom_tools: [
          ...(vmcpData.data.custom_tools || []),
          {
            name: 'health_check',
            description: 'Health check',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/health`,
              headers: {},
              query_params: {},
              auth: { type: 'none' },
            },
            variables: [],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
            source: 'postman_collection',
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const toolsResult = await apiClient.listVMCPTools(createdVMCP.id)
      expect(toolsResult.success).toBe(true)
      const tools = toolsResult.data?.tools || toolsResult.data?.data?.tools || []
      expect(tools.some((t: any) => t.name === 'health_check')).toBe(true)

      console.log('✅ Imported collection tools listed successfully')
    })
  })

  describe('Test 7.3: Call imported collection tool', () => {
    it('should call a tool imported from collection', async () => {
      console.log(`\n📦 Test 7.3 - Calling imported collection tool: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'health_check',
            description: 'Health check endpoint from collection',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/health`,
              headers: {},
              query_params: {},
              auth: { type: 'none' },
            },
            variables: [],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
            source: 'postman_collection',
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'health_check',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200|healthy|success/i)
      }

      console.log('✅ Imported collection tool call successful')
    })
  })

  describe('Test 7.4: Import collection with authentication', () => {
    it('should create tool with authentication from collection', async () => {
      console.log(`\n📦 Test 7.4 - Import collection with auth: ${createdVMCP.id}`)

      // Add environment variables for auth
      await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'api_key', value: 'test-api-key-123' },
        { name: 'bearer_token', value: 'bearer-token-admin' },
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
            name: 'get_users_collection',
            description: 'Get users (from collection)',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/users`,
              headers: {},
              query_params: {},
              auth: {
                type: 'apikey',
                apiKey: '@config.api_key',
                keyName: 'X-API-Key',
              },
            },
            variables: [],
            environment_variables: ['api_key'],
            tool_calls: [],
            atomic_blocks: [],
            source: 'postman_collection',
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.[0]?.source).toBe('postman_collection')

      console.log('✅ Collection with authentication imported successfully')
    })
  })

  describe('Test 7.5: Import collection with path variables', () => {
    it('should create tool with path variables from collection', async () => {
      console.log(`\n📦 Test 7.5 - Import collection with variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'get_user_by_id_collection',
            description: 'Get user by ID (from collection)',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/users/@param.user_id`,
              headers: {},
              query_params: {},
              auth: {
                type: 'bearer',
                token: 'bearer-token-user',
              },
            },
            variables: [
              { name: 'user_id', description: 'User ID', type: 'int', required: true },
            ],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
            source: 'postman_collection',
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      const variables = result.data?.custom_tools?.[0]?.variables
      expect(Array.isArray(variables) ? variables.length : 0).toBe(1)

      console.log('✅ Collection with path variables imported successfully')
    })
  })

  describe('Test 7.6: Import collection with multiple endpoints', () => {
    it('should create multiple tools as if from a collection', async () => {
      console.log(`\n📦 Test 7.6 - Import collection with multiple endpoints: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const endpoints = [
        { name: 'get_health', method: 'GET', url: '/health' },
        { name: 'get_info', method: 'GET', url: '/info' },
        { name: 'get_users', method: 'GET', url: '/users' },
        { name: 'get_products', method: 'GET', url: '/products' },
      ]

      const tools = endpoints.map((endpoint) => ({
        name: endpoint.name,
        description: `${endpoint.method} ${endpoint.url}`,
        tool_type: 'http' as const,
        api_config: {
          method: endpoint.method,
          url: `${TEST_HTTP_SERVER}${endpoint.url}`,
          headers: {},
          query_params: {},
          auth:
            endpoint.url === '/health' || endpoint.url === '/info'
              ? { type: 'none' }
              : {
                  type: 'apikey',
                  apiKey: 'test-api-key-123',
                  keyName: 'X-API-Key',
                },
        },
        variables: [],
        environment_variables: [],
        tool_calls: [],
        atomic_blocks: [],
        source: 'postman_collection',
      }))

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: tools,
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.length).toBe(4)
      expect(result.data?.custom_tools?.every((t: any) => t.source === 'postman_collection')).toBe(
        true
      )

      console.log('✅ Collection with multiple endpoints imported successfully')
    })
  })

  describe('Test 7.7: List multiple imported collection tools', () => {
    it('should list all tools imported from collection', async () => {
      console.log(`\n📦 Test 7.7 - Listing imported collection tools: ${createdVMCP.id}`)

      // Get full vMCP config first (like Python tests do)
      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const tools = []
      for (let i = 0; i < 5; i++) {
        tools.push({
          name: `collection_tool_${i}`,
          description: `Collection tool ${i}`,
          tool_type: 'http' as const,
          api_config: {
            method: 'GET',
            url: `${TEST_HTTP_SERVER}/health`,
            headers: {},
            query_params: {},
            auth: { type: 'none' },
          },
          variables: [],
          environment_variables: [],
          tool_calls: [],
          atomic_blocks: [],
          source: 'postman_collection',
        })
      }

      const updatedConfig: any = {
        id: vmcpData.data.id,
        name: vmcpData.data.name,
        description: vmcpData.data.description,
        system_prompt: vmcpData.data.system_prompt,
        custom_tools: [
          ...(vmcpData.data.custom_tools || []),
          ...tools,
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const toolsResult = await apiClient.listVMCPTools(createdVMCP.id)
      expect(toolsResult.success).toBe(true)
      const listedTools = toolsResult.data?.tools || toolsResult.data?.data?.tools || []

      // Verify all collection tools are listed
      for (let i = 0; i < 5; i++) {
        expect(listedTools.some((t: any) => t.name === `collection_tool_${i}`)).toBe(true)
      }

      console.log(`✅ All ${listedTools.length} imported tools listed successfully`)
    })
  })
})

