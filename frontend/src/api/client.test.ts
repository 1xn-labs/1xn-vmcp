/**
 * API Client Tests
 * 
 * Tests for the API client wrapper to ensure API calls work correctly.
 * Uses Vitest's mocking capabilities to mock HTTP requests.
 * 
 * @see https://vitest.dev/guide/features.html#mocking
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiClient } from './client'
import { client } from './generated/client.gen'
import * as sdk from './generated/sdk.gen'
import type { McpInstallRequest, McpToolCallRequest } from './generated/types.gen'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  healthCheckApiMcpsHealthGet: vi.fn(),
  installMcpServerApiMcpsInstallPost: vi.fn(),
  callMcpToolApiMcpsServerIdToolsCallPost: vi.fn(),
  listMcpServersApiMcpsListGet: vi.fn(),
}))

// Mock fetch for direct API calls
global.fetch = vi.fn()

// Mock the client config
vi.mock('./generated/client.gen', () => ({
  client: {
    setConfig: vi.fn(),
    getConfig: vi.fn(() => ({
      baseUrl: 'http://localhost:8000',
      headers: {},
    })),
  },
}))

describe('ApiClient', () => {
  const mockBaseUrl = 'http://localhost:8000'

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset client config
    vi.mocked(client.setConfig).mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('MCP Server Methods', () => {
    describe('getMCPHealth', () => {
      it('should return success when health check passes', async () => {
        // Arrange
        const mockResponse = {
          data: { status: 'healthy', service: 'MCP service' },
        }
        vi.mocked(sdk.healthCheckApiMcpsHealthGet).mockResolvedValue(mockResponse as any)

        // Act
        const result = await apiClient.getMCPHealth()

        // Assert
        expect(result.success).toBe(true)
        expect(result.data).toEqual(mockResponse.data)
        expect(sdk.healthCheckApiMcpsHealthGet).toHaveBeenCalledOnce()
      })

      it('should return error when health check fails', async () => {
        // Arrange
        const mockError = new Error('Network error')
        vi.mocked(sdk.healthCheckApiMcpsHealthGet).mockRejectedValue(mockError)

        // Act
        const result = await apiClient.getMCPHealth()

        // Assert
        expect(result.success).toBe(false)
        expect(result.error).toBe('Network error')
        expect(result.data).toBeUndefined()
      })
    })

    describe('installMCPServer', () => {
      it('should successfully install an MCP server', async () => {
        // Arrange
        const request: McpInstallRequest = {
          name: 'test-server',
          mode: 'stdio',
          command: 'python',
          args: ['-m', 'test_server'],
        }

        const mockResponse = {
          data: {
            success: true,
            message: 'Server installed successfully',
            data: {
              id: 'server-123',
              name: 'test-server',
              status: 'disconnected',
            },
          },
        }

        vi.mocked(sdk.installMcpServerApiMcpsInstallPost).mockResolvedValue(
          mockResponse as any
        )

        // Act
        const result = await apiClient.installMCPServer(request)

        // Assert
        expect(result.success).toBe(true)
        // The function returns responseData?.server || responseData
        // Since responseData.data doesn't have a 'server' property, it returns responseData (which is mockResponse.data)
        expect(result.data).toEqual(mockResponse.data)
        expect(sdk.installMcpServerApiMcpsInstallPost).toHaveBeenCalledWith({
          body: request,
        })
      })

      it('should handle installation errors', async () => {
        // Arrange
        const request: McpInstallRequest = {
          name: 'test-server',
          mode: 'stdio',
          command: 'python',
        }

        const mockError = new Error('Server already exists')
        vi.mocked(sdk.installMcpServerApiMcpsInstallPost).mockRejectedValue(
          mockError
        )

        // Act
        const result = await apiClient.installMCPServer(request)

        // Assert
        expect(result.success).toBe(false)
        expect(result.error).toBe('Server already exists')
      })

      it('should include authentication token when provided', async () => {
        // Arrange
        const request: McpInstallRequest = {
          name: 'test-server',
          mode: 'stdio',
          command: 'python',
        }
        const token = 'test-token-123'

        const mockResponse = {
          data: {
            success: true,
            data: { id: 'server-123', name: 'test-server' },
          },
        }

        vi.mocked(sdk.installMcpServerApiMcpsInstallPost).mockResolvedValue(
          mockResponse as any
        )

        // Act
        await apiClient.installMCPServer(request, token)

        // Assert
        expect(sdk.installMcpServerApiMcpsInstallPost).toHaveBeenCalledWith({
          body: request,
          headers: { Authorization: 'Bearer test-token-123' },
        })
      })
    })

    describe('callMCPTool', () => {
      it('should successfully call an MCP tool', async () => {
        // Arrange
        const serverId = 'server-123'
        const request: McpToolCallRequest = {
          tool_name: 'search_tool',
          arguments: { query: 'test query', limit: 10 },
        }

        const mockResponse = {
          data: {
            success: true,
            message: 'Tool executed successfully',
            data: {
              content: [{ type: 'text', text: 'Search results here' }],
              tool_name: 'search_tool',
              server: 'server-123',
              server_id: 'server-123',
            },
          },
        }

        vi.mocked(sdk.callMcpToolApiMcpsServerIdToolsCallPost).mockResolvedValue(
          mockResponse as any
        )

        // Act
        const result = await apiClient.callMCPTool(serverId, request)

        // Assert
        expect(result.success).toBe(true)
        expect(result.data).toEqual(mockResponse.data)
        expect(sdk.callMcpToolApiMcpsServerIdToolsCallPost).toHaveBeenCalledWith({
          path: { server_id: serverId },
          body: request,
        })
      })

      it('should handle tool call errors', async () => {
        // Arrange
        const serverId = 'server-123'
        const request: McpToolCallRequest = {
          tool_name: 'invalid_tool',
          arguments: {},
        }

        const mockError = new Error('Tool not found')
        vi.mocked(sdk.callMcpToolApiMcpsServerIdToolsCallPost).mockRejectedValue(
          mockError
        )

        // Act
        const result = await apiClient.callMCPTool(serverId, request)

        // Assert
        expect(result.success).toBe(false)
        expect(result.error).toBe('Tool not found')
      })
    })
  })

  describe('Token Management', () => {
    it('should set and get authentication token', () => {
      // Arrange - Mock getConfig to return the token in headers
      vi.mocked(client.getConfig).mockReturnValue({
        baseUrl: 'http://localhost:8000',
        headers: {
          Authorization: 'Bearer test-token-123',
        },
      } as any)

      // Act
      apiClient.setToken('test-token-123')
      const token = apiClient.getToken()

      // Assert
      expect(token).toBe('test-token-123')
      expect(client.setConfig).toHaveBeenCalledWith({
        headers: {
          Authorization: 'Bearer test-token-123',
        },
      })
    })

    it('should handle undefined token', () => {
      // Act
      apiClient.setToken(undefined)
      const token = apiClient.getToken()

      // Assert
      expect(token).toBeUndefined()
    })
  })

  describe('Direct API Calls (using fetch)', () => {
    describe('login', () => {
      it('should successfully login a user', async () => {
        // Arrange
        const loginRequest = {
          username: 'testuser',
          password: 'testpass123',
        }

        const mockResponse = {
          access_token: 'token-123',
          refresh_token: 'refresh-123',
          token_type: 'bearer',
          expires_in: 3600,
          user: {
            id: 'user-1',
            email: 'test@example.com',
            username: 'testuser',
          },
        }

        vi.mocked(fetch).mockResolvedValue({
          ok: true,
          json: async () => mockResponse,
        } as Response)

        // Act
        const result = await apiClient.login(loginRequest)

        // Assert
        expect(result.success).toBe(true)
        expect(result.data).toEqual(mockResponse)
        expect(fetch).toHaveBeenCalledWith(
          'http://localhost:8000/api/login',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(loginRequest),
          })
        )
      })

      it('should handle login errors', async () => {
        // Arrange
        const loginRequest = {
          username: 'testuser',
          password: 'wrongpass',
        }

        vi.mocked(fetch).mockResolvedValue({
          ok: false,
          status: 401,
          json: async () => ({
            detail: 'Invalid credentials',
          }),
        } as Response)

        // Act
        const result = await apiClient.login(loginRequest)

        // Assert
        expect(result.success).toBe(false)
        expect(result.error).toBe('Invalid credentials')
      })

      it('should handle network errors', async () => {
        // Arrange
        const loginRequest = {
          username: 'testuser',
          password: 'testpass',
        }

        vi.mocked(fetch).mockRejectedValue(new Error('Network error'))

        // Act
        const result = await apiClient.login(loginRequest)

        // Assert
        expect(result.success).toBe(false)
        expect(result.error).toBe('Network error')
      })
    })

    describe('getUserInfo', () => {
      it('should successfully get user info with token', async () => {
        // Arrange
        const token = 'test-token-123'
        const mockUser = {
          id: 'user-1',
          email: 'test@example.com',
          username: 'testuser',
          full_name: 'Test User',
        }

        vi.mocked(fetch).mockResolvedValue({
          ok: true,
          json: async () => mockUser,
        } as Response)

        // Act
        const result = await apiClient.getUserInfo(token)

        // Assert
        expect(result.success).toBe(true)
        expect(result.data).toEqual(mockUser)
        expect(fetch).toHaveBeenCalledWith(
          'http://localhost:8000/api/userinfo',
          expect.objectContaining({
            method: 'GET',
            headers: {
              Authorization: 'Bearer test-token-123',
            },
          })
        )
      })
    })
  })
})

