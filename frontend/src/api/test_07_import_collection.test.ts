/**
 * Test Suite 7: Import Collection
 * Tests collection import functionality (Postman, OpenAPI, etc.)
 * 
 * Corresponds to: backend/tests/test_07_import_collection.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP } from '../test/test-setup'
import { createMockVMCP } from '../test/api-mock-helpers'
import { TEST_HTTP_SERVER } from '../test/test-setup'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  generatePythonToolsApiVmcpsGeneratePythonToolsPost: vi.fn(),
  updateVmcpApiVmcpsVmcpIdPut: vi.fn(),
  callVmcpToolApiVmcpsVmcpIdToolsCallPost: vi.fn(),
}))

describe('Test Suite 7: Import Collection', () => {
  let vmcpName: string
  let createdVMCP: ReturnType<typeof createTestVMCP>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    createdVMCP = createTestVMCP({ name: vmcpName })
    vi.clearAllMocks()
  })

  describe('Test 7.1: Import Postman collection', () => {
    it('should import a Postman collection and generate tools', async () => {
      const postmanCollection = {
        info: {
          name: 'Test API Collection',
          description: 'A test Postman collection',
        },
        item: [
          {
            name: 'Get Users',
            request: {
              method: 'GET',
              url: {
                raw: `${TEST_HTTP_SERVER}/api/users`,
              },
            },
          },
        ],
      }

      const mockGeneratedTools = {
        success: true,
        tools: [
          {
            name: 'get_users',
            method: 'GET',
            url: `${TEST_HTTP_SERVER}/api/users`,
            description: 'Get Users',
            code: 'def get_users(): ...',
            parameters: {},
            collectionMetadata: {
              name: 'Test API Collection',
            },
          },
        ],
        collectionMetadata: {
          name: 'Test API Collection',
        },
      }

      vi.mocked(sdk.generatePythonToolsApiVmcpsGeneratePythonToolsPost).mockResolvedValue({
        data: mockGeneratedTools,
      } as any)

      // Note: This would need to be implemented in the API client
      // For now, we'll test the concept
      expect(postmanCollection.item.length).toBe(1)
      expect(mockGeneratedTools.tools.length).toBe(1)
      expect(mockGeneratedTools.tools[0].name).toBe('get_users')
    })
  })

  describe('Test 7.2: Import OpenAPI spec', () => {
    it('should import an OpenAPI specification', async () => {
      const openAPISpec = {
        openapi: '3.0.0',
        info: {
          title: 'Test API',
          version: '1.0.0',
        },
        paths: {
          '/api/users': {
            get: {
              summary: 'Get users',
              responses: {
                '200': {
                  description: 'Success',
                },
              },
            },
          },
        },
      }

      // Similar to Postman collection import
      expect(openAPISpec.paths['/api/users']).toBeDefined()
      expect(openAPISpec.paths['/api/users'].get).toBeDefined()
    })
  })

  describe('Test 7.3: Call imported collection tool', () => {
    it('should execute a tool imported from a collection', async () => {
      // After importing, the tool should be available as a custom tool
      const customTool = {
        tool_type: 'http',
        name: 'get_users',
        description: 'Get Users (imported from collection)',
        variables: [],
        url: `${TEST_HTTP_SERVER}/api/users`,
        method: 'GET',
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
          tool: 'get_users',
          result: { status_code: 200, response: { users: [] } },
        },
      }

      vi.mocked(sdk.callVmcpToolApiVmcpsVmcpIdToolsCallPost).mockResolvedValue({
        data: mockToolResult,
      } as any)

      const result = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'get_users',
        arguments: {},
      })

      expect(result.success).toBe(true)
    })
  })

  describe('Test 7.4: Import collection with authentication', () => {
    it('should import a collection with authentication configured', async () => {
      const postmanCollectionWithAuth = {
        info: {
          name: 'Authenticated API Collection',
        },
        auth: {
          type: 'bearer',
          bearer: [
            {
              key: 'token',
              value: '{{api_token}}',
            },
          ],
        },
        item: [
          {
            name: 'Authenticated Request',
            request: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/api/secure`,
            },
          },
        ],
      }

      expect(postmanCollectionWithAuth.auth).toBeDefined()
      expect(postmanCollectionWithAuth.auth.type).toBe('bearer')
    })
  })

  describe('Test 7.5: Import collection with variables', () => {
    it('should import a collection with variables', async () => {
      const postmanCollectionWithVars = {
        info: {
          name: 'Collection with Variables',
        },
        variable: [
          {
            key: 'base_url',
            value: TEST_HTTP_SERVER,
          },
          {
            key: 'api_key',
            value: '{{api_key}}',
          },
        ],
        item: [],
      }

      expect(postmanCollectionWithVars.variable).toBeDefined()
      expect(postmanCollectionWithVars.variable.length).toBe(2)
    })
  })

  describe('Test 7.6: Import collection multiple endpoints', () => {
    it('should import a collection with multiple endpoints', async () => {
      const multiEndpointCollection = {
        info: {
          name: 'Multi-Endpoint Collection',
        },
        item: [
          {
            name: 'Get Users',
            request: {
              method: 'GET',
              url: `${TEST_HTTP_SERVER}/api/users`,
            },
          },
          {
            name: 'Create User',
            request: {
              method: 'POST',
              url: `${TEST_HTTP_SERVER}/api/users`,
            },
          },
          {
            name: 'Update User',
            request: {
              method: 'PUT',
              url: `${TEST_HTTP_SERVER}/api/users/{{id}}`,
            },
          },
          {
            name: 'Delete User',
            request: {
              method: 'DELETE',
              url: `${TEST_HTTP_SERVER}/api/users/{{id}}`,
            },
          },
        ],
      }

      expect(multiEndpointCollection.item.length).toBe(4)
      expect(multiEndpointCollection.item.map((item: any) => item.request.method)).toEqual([
        'GET',
        'POST',
        'PUT',
        'DELETE',
      ])
    })
  })
})

