/**
 * Integration Test Suite 1: vMCP Creation
 * Tests basic vMCP creation and validation with REAL API calls
 * 
 * Requires: Backend server running on localhost:8000
 * 
 * Corresponds to: backend/tests/test_01_vmcp_creation.py
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { apiClient } from './client'
import {
  setupIntegrationTests,
  requireBackend,
  createVMCPForTest,
  wait,
} from '../test/integration-setup'
import { generateVMCPName } from '../test/test-setup'

// Setup integration test environment
setupIntegrationTests()

describe('Integration Test Suite 1: vMCP Creation', () => {
  beforeAll(async () => {
    // Ensure backend is available
    await requireBackend()
  })

  describe('Test 1.1: Create a basic vMCP', () => {
    it('should create a vMCP with name and description', async () => {
      const vmcpName = generateVMCPName()
      console.log(`\n📦 Test 1.1 - Creating vMCP: ${vmcpName}`)

      const result = await apiClient.createVMCP({
        name: vmcpName,
        description: 'Test vMCP for basic creation',
      })

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      expect(result.data?.name).toBe(vmcpName)
      expect(result.data?.description).toBe('Test vMCP for basic creation')
      expect(result.data?.id).toBeDefined()

      console.log(`✅ vMCP created with ID: ${result.data?.id}`)

      // Cleanup - delete immediately (not registering for afterAll cleanup)
      if (result.data?.id) {
        await apiClient.deleteVMCP(result.data.id)
      }
    })
  })

  describe('Test 1.2: Create vMCP with system prompt', () => {
    it('should create a vMCP with system prompt', async () => {
      const vmcpName = generateVMCPName()
      console.log(`\n📦 Test 1.2 - Creating vMCP with system prompt: ${vmcpName}`)

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

      console.log('✅ vMCP created with system prompt')

      // Cleanup - delete immediately (not registering for afterAll cleanup)
      if (result.data?.id) {
        await apiClient.deleteVMCP(result.data.id)
      }
    })
  })

  describe('Test 1.3: Get vMCP details', () => {
    it('should retrieve vMCP details by ID', async () => {
      const vmcp = await createVMCPForTest(generateVMCPName())
      console.log(`\n📦 Test 1.3 - Retrieving vMCP details: ${vmcp.id}`)

      const result = await apiClient.getVMCPDetails(vmcp.id)

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      expect(result.data?.id).toBe(vmcp.id)
      expect(result.data?.name).toBe(vmcp.name)
      expect(result.data?.created_at).toBeDefined()

      console.log('✅ vMCP details retrieved successfully')

      // Cleanup handled by createVMCPForTest
    })
  })

  describe('Test 1.4: List vMCPs', () => {
    it('should retrieve list of vMCPs', async () => {
      // Create a test vMCP first
      const vmcp = await createVMCPForTest(generateVMCPName())
      console.log('\n📦 Test 1.4 - Listing all vMCPs')

      // Wait a bit for the server to process
      await wait(200)

      const result = await apiClient.listVMCPS()

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      expect(result.data?.private).toBeDefined()
      expect(Array.isArray(result.data?.private)).toBe(true)

      // Should contain our created vMCP
      const foundVMCP = result.data?.private.find((v: any) => v.id === vmcp.id)
      expect(foundVMCP).toBeDefined()

      console.log(`✅ Found ${result.data?.private.length} vMCPs`)

      // Cleanup handled by createVMCPForTest
    })
  })

  describe('Test 1.5: Update vMCP description', () => {
    it('should update vMCP description', async () => {
      const vmcp = await createVMCPForTest(generateVMCPName())
      console.log(`\n📦 Test 1.5 - Updating vMCP description: ${vmcp.id}`)

      const result = await apiClient.updateVMCP(vmcp.id, {
        description: 'Updated description',
      })

      expect(result.success).toBe(true)
      expect(result.data?.description).toBe('Updated description')

      console.log('✅ vMCP description updated successfully')

      // Cleanup handled by createVMCPForTest
    })
  })

  describe('Test 1.6: Delete vMCP', () => {
    it('should delete a vMCP successfully', async () => {
      // Create vMCP manually (not using createVMCPForTest to avoid automatic cleanup registration)
      const vmcpName = generateVMCPName()
      const createResult = await apiClient.createVMCP({
        name: vmcpName,
        description: 'Test vMCP for deletion',
      })

      if (!createResult.success || !createResult.data) {
        throw new Error(`Failed to create vMCP: ${createResult.error}`)
      }

      const vmcp = createResult.data
      console.log(`\n📦 Test 1.6 - Deleting vMCP: ${vmcp.id}`)

      const result = await apiClient.deleteVMCP(vmcp.id)

      expect(result.success).toBe(true)

      // After deletion, the vMCP might still be returned but should be marked as deleted
      // or not appear in the list. Check the list instead.
      const listResult = await apiClient.listVMCPS()
      if (listResult.success && listResult.data) {
        const privateVMCPs = listResult.data.private || []
        const deletedVMCPInList = privateVMCPs.find((v: any) => v.id === vmcp.id)
        // The deleted vMCP should not be in the list
        expect(deletedVMCPInList).toBeUndefined()
      }

      console.log('✅ vMCP deleted successfully')
    })
  })

  describe('Test 1.7: Health check', () => {
    it('should check vMCP service health', async () => {
      console.log('\n📦 Test 1.7 - Checking vMCP service health')

      const result = await apiClient.getVMCPHealth()

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()

      console.log('✅ Health check successful')
    })
  })
})

