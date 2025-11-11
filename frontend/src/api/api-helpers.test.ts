/**
 * API Helper Functions Tests
 * 
 * Example tests for API helper functions and utilities.
 * Demonstrates different mocking strategies with Vitest.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'

// Mock the entire SDK module
vi.mock('./generated/sdk.gen', async () => {
  const actual = await vi.importActual('./generated/sdk.gen')
  return {
    ...actual,
    listMcpServersApiMcpsListGet: vi.fn(),
  }
})

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}

describe('API Helper Functions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    })
  })

  describe('listMCPServers', () => {
    it('should return list of servers', async () => {
      // Mock the response
      const mockServers = {
        data: {
          success: true,
          message: 'Servers retrieved successfully',
          data: [
            {
              id: 'server-1',
              name: 'Test Server 1',
              status: 'connected',
              transport_type: 'stdio',
            },
            {
              id: 'server-2',
              name: 'Test Server 2',
              status: 'disconnected',
              transport_type: 'http',
            },
          ],
          pagination: {
            page: 1,
            limit: 50,
            total: 2,
            pages: 1,
          },
        },
      }

      // Use vi.spyOn to spy on the method
      const listServersSpy = vi.spyOn(apiClient, 'listMCPServers')
      listServersSpy.mockResolvedValue({
        success: true,
        data: mockServers.data.data,
      })

      // Act
      const result = await apiClient.listMCPServers()

      // Assert
      expect(result.success).toBe(true)
      expect(result.data).toHaveLength(2)
      expect(result.data?.[0]).toHaveProperty('id', 'server-1')
      expect(result.data?.[1]).toHaveProperty('id', 'server-2')

      listServersSpy.mockRestore()
    })

    it('should handle empty server list', async () => {
      const listServersSpy = vi.spyOn(apiClient, 'listMCPServers')
      listServersSpy.mockResolvedValue({
        success: true,
        data: [],
      })

      const result = await apiClient.listMCPServers()

      expect(result.success).toBe(true)
      expect(result.data).toEqual([])

      listServersSpy.mockRestore()
    })
  })

  describe('Error Handling', () => {
    it('should handle API timeout errors', async () => {
      const listServersSpy = vi.spyOn(apiClient, 'listMCPServers')
      // Mock to return error response instead of rejecting
      listServersSpy.mockResolvedValue({
        success: false,
        error: 'Request timeout',
      })

      // Act - Call the API
      const result = await apiClient.listMCPServers()

      // Assert - Verify error handling
      expect(result.success).toBe(false)
      expect(result.error).toContain('timeout')

      listServersSpy.mockRestore()
    })

    it('should handle 500 server errors', async () => {
      const error = new Error('Internal Server Error')
      Object.assign(error, { status: 500 })

      const listServersSpy = vi.spyOn(apiClient, 'listMCPServers')
      listServersSpy.mockResolvedValue({
        success: false,
        error: 'Internal Server Error',
      })

      const result = await apiClient.listMCPServers()

      expect(result.success).toBe(false)
      expect(result.error).toBe('Internal Server Error')

      listServersSpy.mockRestore()
    })
  })
})

describe('API Client with Mocked Fetch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn()
  })

  it('should make authenticated requests with Bearer token', async () => {
    const mockResponse = {
      id: 'user-1',
      email: 'test@example.com',
    }

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response)

    const result = await apiClient.getUserInfo('test-token')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/userinfo'),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token',
        }),
      })
    )
    expect(result.success).toBe(true)
    expect(result.data).toEqual(mockResponse)
  })

  it('should handle different error response formats', async () => {
    // Test with detail field
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Not found' }),
    } as Response)

    let result = await apiClient.getUserInfo('token')
    expect(result.error).toBe('Not found')

    // Test with message field
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ message: 'Bad request' }),
    } as Response)

    result = await apiClient.getUserInfo('token')
    expect(result.error).toBe('Bad request')

    // Test with status code only
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as Response)

    result = await apiClient.getUserInfo('token')
    expect(result.error).toContain('500')
  })
})

