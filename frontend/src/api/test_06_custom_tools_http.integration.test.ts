/**
 * Integration Test Suite 6: Custom Tools - HTTP Type
 * Tests for HTTP-based custom tools with various authentication methods with REAL API calls
 * 
 * Requires: 
 * - Backend server running on localhost:8000
 * - Test HTTP server running on localhost:8002
 * 
 * Corresponds to: backend/tests/test_06_custom_tools_http.py
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

describe('Integration Test Suite 6: Custom Tools - HTTP Type', () => {
  let createdVMCP: Awaited<ReturnType<typeof createVMCPForTest>>

  beforeAll(async () => {
    await requireBackend()
    createdVMCP = await createVMCPForTest(generateVMCPName())
  })

  describe('Test 6.1: Create a simple HTTP GET tool', () => {
    it('should create a simple HTTP GET tool', async () => {
      console.log(`\n📦 Test 6.1 - Creating simple HTTP GET tool: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'get_server_health',
            description: 'Get server health status',
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
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.length).toBe(1)
      expect(result.data?.custom_tools?.[0]?.tool_type).toBe('http')

      console.log('✅ Simple HTTP GET tool created successfully')
    })
  })

  describe('Test 6.2: Call HTTP GET tool', () => {
    it('should call HTTP GET tool', async () => {
      console.log(`\n📦 Test 6.2 - Calling HTTP GET tool: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'fetch_health',
            description: 'Fetch health status',
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
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'fetch_health',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        const text = result.data.content[0].text
        expect(text).toMatch(/200|healthy|success/i)
      }

      console.log('✅ HTTP GET tool call successful')
    })
  })

  describe('Test 6.3: HTTP tool with API key header', () => {
    it('should call HTTP tool with API key header authentication', async () => {
      console.log(`\n📦 Test 6.3 - HTTP tool with API key header: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'get_users_with_apikey',
            description: 'Get users with API key',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/users`,
              headers: {},
              query_params: {},
              auth: {
                type: 'apikey',
                apiKey: 'test-api-key-123',
                keyName: 'X-API-Key',
              },
            },
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
        tool_name: 'get_users_with_apikey',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200/i)
      }

      console.log('✅ HTTP tool with API key header successful')
    })
  })

  describe('Test 6.4: HTTP tool with Bearer token', () => {
    it('should call HTTP tool with Bearer token authentication', async () => {
      console.log(`\n📦 Test 6.4 - HTTP tool with Bearer token: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'get_user_profile',
            description: 'Get user profile',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/users/1`,
              headers: {},
              query_params: {},
              auth: {
                type: 'bearer',
                token: 'bearer-token-admin',
              },
            },
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
        tool_name: 'get_user_profile',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200/i)
      }

      console.log('✅ HTTP tool with Bearer token successful')
    })
  })

  describe('Test 6.5: HTTP tool with Basic auth', () => {
    it('should call HTTP tool with Basic authentication', async () => {
      console.log(`\n📦 Test 6.5 - HTTP tool with Basic auth: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'create_user',
            description: 'Create a new user',
            tool_type: 'http',
            api_config: {
              method: 'POST',
              url: `${TEST_HTTP_SERVER}/users`,
              headers: { 'Content-Type': 'application/json' },
              query_params: {},
              body_parsed: {
                username: 'testuser',
                email: 'test@example.com',
                full_name: 'Test User',
                password: 'testpass123',
              },
              auth: {
                type: 'basic',
                username: 'admin',
                password: 'admin123',
              },
            },
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
        tool_name: 'create_user',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        // Might get 200 or 400 if user exists
        expect(result.data.content[0].text).toMatch(/200|400/i)
      }

      console.log('✅ HTTP tool with Basic auth successful')
    })
  })

  describe('Test 6.6: HTTP tool with query parameters', () => {
    it('should call HTTP tool with query parameters', async () => {
      console.log(`\n📦 Test 6.6 - HTTP tool with query parameters: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'get_products_filtered',
            description: 'Get filtered products',
            tool_type: 'http',
            api_config: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/products`,
              headers: {},
              query_params: {
                category: 'Electronics',
                in_stock: 'true',
                api_key: 'test-api-key-123',
              },
              auth: { type: 'none' },
            },
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
        tool_name: 'get_products_filtered',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200/i)
      }

      console.log('✅ HTTP tool with query parameters successful')
    })
  })

  describe('Test 6.7: HTTP tool with @param substitution', () => {
    it('should call HTTP tool with param variable substitution', async () => {
      console.log(`\n📦 Test 6.7 - HTTP tool with param substitution: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'get_user_by_id',
            description: 'Get user by ID',
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
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'get_user_by_id',
        arguments: { user_id: 2 },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200/i)
      }

      console.log('✅ HTTP tool with param substitution successful')
    })
  })

  describe('Test 6.8: HTTP tool with @config substitution', () => {
    it('should call HTTP tool with config variable substitution', async () => {
      console.log(`\n📦 Test 6.8 - HTTP tool with config substitution: ${createdVMCP.id}`)

      // Add environment variables
      await apiClient.saveVMCPEnvironmentVariables(createdVMCP.id, [
        { name: 'api_key', value: 'test-api-key-123' },
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
            name: 'get_users_with_config',
            description: 'Get users using config API key',
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
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'get_users_with_config',
        arguments: {},
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200/i)
      }

      console.log('✅ HTTP tool with config substitution successful')
    })
  })

  describe('Test 6.9: HTTP POST with JSON body', () => {
    it('should call HTTP POST tool with JSON body and param substitution', async () => {
      console.log(`\n📦 Test 6.9 - HTTP POST with JSON body: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'create_product',
            description: 'Create a new product',
            tool_type: 'http',
            api_config: {
              method: 'POST',
              url: `${TEST_HTTP_SERVER}/products`,
              headers: { 'Content-Type': 'application/json' },
              query_params: {},
              body_parsed: {
                name: '@param.product_name',
                description: '@param.description',
                price: '@param.price',
                category: '@param.category',
                in_stock: true,
                tags: [],
                metadata: {},
              },
              auth: {
                type: 'bearer',
                token: 'bearer-token-admin',
              },
            },
            variables: [
              { name: 'product_name', description: 'Product name', type: 'str', required: true },
              { name: 'description', description: 'Product description', type: 'str', required: true },
              { name: 'price', description: 'Product price', type: 'float', required: true },
              { name: 'category', description: 'Product category', type: 'str', required: true },
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
        tool_name: 'create_product',
        arguments: {
          product_name: 'Test Keyboard',
          description: 'Mechanical keyboard',
          price: 99.99,
          category: 'Electronics',
        },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200/i)
      }

      console.log('✅ HTTP POST with JSON body successful')
    })
  })

  describe('Test 6.10: HTTP PATCH method', () => {
    it('should call HTTP PATCH tool', async () => {
      console.log(`\n📦 Test 6.10 - HTTP PATCH method: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'update_product_price',
            description: 'Update product price',
            tool_type: 'http',
            api_config: {
              method: 'PATCH',
              url: `${TEST_HTTP_SERVER}/products/@param.product_id`,
              headers: { 'Content-Type': 'application/json' },
              query_params: {},
              body_parsed: {
                price: '@param.new_price',
              },
              auth: {
                type: 'bearer',
                token: 'bearer-token-admin',
              },
            },
            variables: [
              { name: 'product_id', description: 'Product ID', type: 'int', required: true },
              { name: 'new_price', description: 'New price', type: 'float', required: true },
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
        tool_name: 'update_product_price',
        arguments: { product_id: 1, new_price: 899.99 },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toMatch(/200/i)
      }

      console.log('✅ HTTP PATCH method successful')
    })
  })
})

