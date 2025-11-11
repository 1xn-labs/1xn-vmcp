/**
 * Test Suite 1: vMCP Creation
 * Tests basic vMCP creation and validation
 * 
 * Corresponds to: backend/tests/test_01_vmcp_creation.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient } from './client'
import * as sdk from './generated/sdk.gen'
import { generateVMCPName, createTestVMCP, createTestHelpers } from '../test/test-setup'
import { createMockVMCP } from '../test/api-mock-helpers'
import type { VmcpConfig } from './generated/types.gen'

// Mock the generated SDK
vi.mock('./generated/sdk.gen', () => ({
  createVmcpApiVmcpsCreatePost: vi.fn(),
  getVmcpDetailsApiVmcpsVmcpIdGet: vi.fn(),
  listVmcpsApiVmcpsListGet: vi.fn(),
  updateVmcpApiVmcpsVmcpIdPut: vi.fn(),
  deleteVmcpApiVmcpsVmcpIdDelete: vi.fn(),
  healthCheckApiVmcpsHealthGet: vi.fn(),
}))

describe('Test Suite 1: vMCP Creation', () => {
  let vmcpName: string
  let helpers: ReturnType<typeof createTestHelpers>

  beforeEach(() => {
    vmcpName = generateVMCPName()
    helpers = createTestHelpers()
    vi.clearAllMocks()
  })

  describe('Test 1.1: Create a basic vMCP', () => {
    it('should create a vMCP with name and description', async () => {
      const mockVMCP = createMockVMCP({
        name: vmcpName,
        description: 'Test vMCP for basic creation',
      })

      vi.mocked(sdk.createVmcpApiVmcpsCreatePost).mockResolvedValue({
        data: {
          vMCP: mockVMCP,
        },
      } as any)

      const result = await apiClient.createVMCP({
        name: vmcpName,
        description: 'Test vMCP for basic creation',
      })

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      expect(result.data?.name).toBe(vmcpName)
      expect(result.data?.description).toBe('Test vMCP for basic creation')
      expect(sdk.createVmcpApiVmcpsCreatePost).toHaveBeenCalledWith({
        body: {
          name: vmcpName,
          description: 'Test vMCP for basic creation',
        },
      })
    })

    it('should handle API errors when creating vMCP', async () => {
      vi.mocked(sdk.createVmcpApiVmcpsCreatePost).mockRejectedValue(
        new Error('Server error')
      )

      const result = await apiClient.createVMCP({
        name: vmcpName,
        description: 'Test vMCP',
      })

      expect(result.success).toBe(false)
      expect(result.error).toContain('Server error')
    })
  })

  describe('Test 1.2: Create vMCP with system prompt', () => {
    it('should create a vMCP with system prompt', async () => {
      const mockVMCP = createMockVMCP({
        name: vmcpName,
        system_prompt: {
          text: 'You are a helpful assistant',
          variables: [],
        },
      })

      vi.mocked(sdk.createVmcpApiVmcpsCreatePost).mockResolvedValue({
        data: {
          vMCP: mockVMCP,
        },
      } as any)

      const result = await apiClient.createVMCP({
        name: vmcpName,
        description: 'Test vMCP with system prompt',
        system_prompt: {
          text: 'You are a helpful assistant',
          variables: [],
        },
      })

      expect(result.success).toBe(true)
      expect(result.data?.system_prompt).toBeDefined()
      expect(result.data?.system_prompt?.text).toBe('You are a helpful assistant')
    })
  })

  describe('Test 1.3: Get vMCP details', () => {
    it('should retrieve vMCP details by ID', async () => {
      const mockVMCP = createMockVMCP({
        id: 'vmcp-123',
        name: vmcpName,
      })

      vi.mocked(sdk.getVmcpDetailsApiVmcpsVmcpIdGet).mockResolvedValue({
        data: mockVMCP,
      } as any)

      const result = await apiClient.getVMCPDetails('vmcp-123')

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      expect(result.data?.id).toBe('vmcp-123')
      expect(result.data?.name).toBe(vmcpName)
      expect(sdk.getVmcpDetailsApiVmcpsVmcpIdGet).toHaveBeenCalledWith({
        path: { vmcp_id: 'vmcp-123' },
      })
    })

    it('should handle errors when vMCP not found', async () => {
      vi.mocked(sdk.getVmcpDetailsApiVmcpsVmcpIdGet).mockRejectedValue(
        new Error('vMCP not found')
      )

      const result = await apiClient.getVMCPDetails('nonexistent-id')

      expect(result.success).toBe(false)
      expect(result.error).toContain('not found')
    })
  })

  describe('Test 1.4: List vMCPs', () => {
    it('should retrieve list of vMCPs', async () => {
      const mockVMCPS = [
        createMockVMCP({ id: 'vmcp-1', name: 'VMCP 1' }),
        createMockVMCP({ id: 'vmcp-2', name: 'VMCP 2' }),
      ]

      vi.mocked(sdk.listVmcpsApiVmcpsListGet).mockResolvedValue({
        data: {
          private: mockVMCPS,
          public: [],
        },
      } as any)

      const result = await apiClient.listVMCPS()

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      expect(result.data?.private).toBeDefined()
      expect(result.data?.private.length).toBe(2)
      expect(result.data?.private[0].name).toBe('VMCP 1')
      expect(result.data?.private[1].name).toBe('VMCP 2')
    })

    it('should handle empty vMCP list', async () => {
      vi.mocked(sdk.listVmcpsApiVmcpsListGet).mockResolvedValue({
        data: {
          private: [],
          public: [],
        },
      } as any)

      const result = await apiClient.listVMCPS()

      expect(result.success).toBe(true)
      expect(result.data?.private).toEqual([])
      expect(result.data?.public).toEqual([])
    })
  })

  describe('Test 1.5: Update vMCP description', () => {
    it('should update vMCP description', async () => {
      const updatedVMCP = createMockVMCP({
        id: 'vmcp-123',
        name: vmcpName,
        description: 'Updated description',
      })

      vi.mocked(sdk.updateVmcpApiVmcpsVmcpIdPut).mockResolvedValue({
        data: {
          vMCP: updatedVMCP,
        },
      } as any)

      const result = await apiClient.updateVMCP('vmcp-123', {
        description: 'Updated description',
      })

      expect(result.success).toBe(true)
      expect(result.data?.description).toBe('Updated description')
      expect(sdk.updateVmcpApiVmcpsVmcpIdPut).toHaveBeenCalledWith({
        path: { vmcp_id: 'vmcp-123' },
        body: {
          description: 'Updated description',
        },
      })
    })
  })

  describe('Test 1.6: Delete vMCP', () => {
    it('should delete a vMCP successfully', async () => {
      vi.mocked(sdk.deleteVmcpApiVmcpsVmcpIdDelete).mockResolvedValue({
        data: {
          success: true,
          message: 'vMCP deleted successfully',
        },
      } as any)

      const result = await apiClient.deleteVMCP('vmcp-123')

      expect(result.success).toBe(true)
      expect(sdk.deleteVmcpApiVmcpsVmcpIdDelete).toHaveBeenCalledWith({
        path: { vmcp_id: 'vmcp-123' },
      })
    })
  })

  describe('Test 1.7: Health check', () => {
    it('should check vMCP service health', async () => {
      vi.mocked(sdk.healthCheckApiVmcpsHealthGet).mockResolvedValue({
        data: {
          status: 'healthy',
          service: 'vMCP service',
        },
      } as any)

      const result = await apiClient.getVMCPHealth()

      expect(result.success).toBe(true)
      expect(result.data?.status).toBe('healthy')
    })
  })
})

