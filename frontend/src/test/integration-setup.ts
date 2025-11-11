/**
 * Integration Test Setup
 * 
 * Provides utilities for integration tests that make real API calls.
 * These tests require the backend server to be running.
 */

import { beforeAll, afterAll, beforeEach } from 'vitest'
import { apiClient, updateApiToken } from '../api/client'
import { BASE_URL } from './test-setup'
import type { VmcpConfig } from '../api/generated/types.gen'

// Track created resources for cleanup
const createdVMCPS: string[] = []
const createdServers: string[] = []

/**
 * Check if backend server is running
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/api/mcps/health`)
    return response.ok
  } catch {
    return false
  }
}

/**
 * Skip tests if backend is not available
 */
export async function requireBackend() {
  const isAvailable = await checkBackendHealth()
  if (!isAvailable) {
    throw new Error(
      `Backend server is not available at ${BASE_URL}. ` +
      'Please start the backend server before running integration tests.'
    )
  }
  return true
}

/**
 * Setup integration tests - check backend availability
 */
export function setupIntegrationTests() {
  beforeAll(async () => {
    // Check if backend is running
    const isAvailable = await checkBackendHealth()
    if (!isAvailable) {
      console.warn(
        `⚠️  Backend server not available at ${BASE_URL}. ` +
        'Integration tests will be skipped. Start the backend with: ' +
        'cd backend && python -m uvicorn src.vmcp.main:app --reload --port 8000'
      )
    }

    // Set up API client with test token (or local-token for OSS mode)
    const token = localStorage.getItem('access_token') || 'local-token'
    updateApiToken(token)
  })

  beforeEach(() => {
    // Clear created resources list for each test
    // (cleanup happens in afterAll)
  })

  afterAll(async () => {
    // Cleanup: Delete all created vMCPs
    for (const vmcpId of createdVMCPS) {
      try {
        await apiClient.deleteVMCP(vmcpId)
      } catch (error) {
        console.warn(`Failed to cleanup vMCP ${vmcpId}:`, error)
      }
    }

    // Cleanup: Uninstall all created servers
    for (const serverId of createdServers) {
      try {
        const uninstallResult = await apiClient.uninstallMCPServer(serverId)
        // Only log warning if it's not a 404 (server might already be cleaned up)
        if (!uninstallResult.success && uninstallResult.error && !uninstallResult.error.includes('404')) {
          console.warn(`Failed to cleanup server ${serverId}:`, uninstallResult.error)
        }
      } catch (error) {
        // Ignore 404 errors (server already cleaned up)
        const errorMsg = error instanceof Error ? error.message : String(error)
        if (!errorMsg.includes('404')) {
          console.warn(`Failed to cleanup server ${serverId}:`, error)
        }
      }
    }

    // Clear tracking arrays
    createdVMCPS.length = 0
    createdServers.length = 0
  })
}

/**
 * Register a vMCP for cleanup
 */
export function registerVMCPForCleanup(vmcpId: string) {
  createdVMCPS.push(vmcpId)
}

/**
 * Register a server for cleanup
 */
export function registerServerForCleanup(serverId: string) {
  createdServers.push(serverId)
}

/**
 * Wait for async operations to complete
 */
export async function wait(ms: number = 100): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Create a vMCP and register for cleanup
 */
export async function createVMCPForTest(
  name: string,
  description?: string
): Promise<VmcpConfig> {
  await requireBackend()

  const result = await apiClient.createVMCP({
    name,
    description: description || `Test vMCP: ${name}`,
  })

  if (!result.success || !result.data) {
    throw new Error(`Failed to create vMCP: ${result.error}`)
  }

  registerVMCPForCleanup(result.data.id)
  return result.data
}

/**
 * Create an MCP server and register for cleanup
 */
export async function createMCPServerForTest(serverData: {
  name: string
  mode: 'stdio' | 'http' | 'sse'
  url?: string
  command?: string
  args?: string[]
  description?: string
}): Promise<string> {
  await requireBackend()

  const result = await apiClient.installMCPServer(serverData as any)

  if (!result.success || !result.data) {
    throw new Error(`Failed to install MCP server: ${result.error}`)
  }

  // Extract server ID from various possible response structures
  const serverId = 
    result.data.id || 
    result.data.server_id || 
    (result.data as any)?.data?.id ||
    serverData.name
  
  registerServerForCleanup(serverId)
  return serverId
}

