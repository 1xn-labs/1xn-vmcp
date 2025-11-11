/**
 * Test Setup and Fixtures
 * 
 * Provides test fixtures and helpers similar to backend conftest.py
 */

import { beforeEach, afterEach, vi } from 'vitest'
import { apiClient } from '../api/client'
import type { VmcpConfig, McpServerInfo } from '../api/generated/types.gen'
import { createMockVMCP, createMockMCPServer } from './api-mock-helpers'

// Base URL for API calls (can be overridden in tests)
export const BASE_URL = 'http://localhost:8000'

// Test MCP server URLs (matching backend conftest.py)
export const MCP_SERVERS = {
  everything: 'http://localhost:8001/everything/mcp',
  allfeature: 'http://localhost:8001/allfeature/mcp',
}

// Test HTTP server URL
export const TEST_HTTP_SERVER = 'http://localhost:8002'

/**
 * Generate a unique vMCP name for each test
 */
export function generateVMCPName(): string {
  const uuid = `${Date.now()}-${Math.random().toString(36).substring(2, 15)}`
  return `test_vmcp_${uuid.substring(0, 12)}`
}

/**
 * Create a mock vMCP for testing
 */
export function createTestVMCP(overrides?: Partial<VmcpConfig>): VmcpConfig {
  const name = generateVMCPName()
  return {
    id: `vmcp-${Date.now()}`,
    name,
    description: 'Test vMCP',
    status: 'active',
    user_id: 'test-user-123',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    custom_prompts: [],
    custom_tools: [],
    custom_resources: [],
    custom_resource_templates: [],
    custom_widgets: [],
    environment_variables: [],
    uploaded_files: [],
    custom_resource_uris: [],
    vmcp_config: {
      selected_servers: [],
      selected_tools: {},
      selected_prompts: {},
      selected_resources: {},
    },
    ...overrides,
  } as VmcpConfig
}

/**
 * Create a mock MCP server for testing
 */
export function createTestMCPServer(overrides?: Partial<McpServerInfo>): McpServerInfo {
  return createMockMCPServer({
    name: `test-server-${Date.now()}`,
    ...overrides,
  })
}

/**
 * Helper functions for API operations (similar to backend helpers fixture)
 */
export interface TestHelpers {
  getVMCP: (vmcpId: string) => Promise<VmcpConfig>
  updateVMCP: (vmcpId: string, data: any) => Promise<VmcpConfig>
  addServer: (vmcpId: string, serverData: any) => Promise<any>
  saveEnvVars: (vmcpId: string, envVars: any[]) => Promise<any>
  deleteVMCP: (vmcpId: string) => Promise<void>
}

/**
 * Create test helpers with mocked API client
 */
export function createTestHelpers(): TestHelpers {
  return {
    getVMCP: async (vmcpId: string) => {
      const result = await apiClient.getVMCPDetails(vmcpId)
      if (!result.success || !result.data) {
        throw new Error(`Failed to get vMCP: ${result.error}`)
      }
      return result.data as VmcpConfig
    },
    
    updateVMCP: async (vmcpId: string, data: any) => {
      const result = await apiClient.updateVMCP(vmcpId, data)
      if (!result.success || !result.data) {
        throw new Error(`Failed to update vMCP: ${result.error}`)
      }
      return result.data as VmcpConfig
    },
    
    addServer: async (vmcpId: string, serverData: any) => {
      const result = await apiClient.addServerToVMCP(vmcpId, serverData)
      if (!result.success) {
        throw new Error(`Failed to add server: ${result.error}`)
      }
      return result.data
    },
    
    saveEnvVars: async (vmcpId: string, envVars: any[]) => {
      const result = await apiClient.saveVMCPEnvironmentVariables(vmcpId, envVars)
      if (!result.success) {
        throw new Error(`Failed to save environment variables: ${result.error}`)
      }
      return result.data
    },
    
    deleteVMCP: async (vmcpId: string) => {
      const result = await apiClient.deleteVMCP(vmcpId)
      if (!result.success) {
        throw new Error(`Failed to delete vMCP: ${result.error}`)
      }
    },
  }
}

/**
 * Setup test environment before each test
 */
export function setupTestEnvironment() {
  beforeEach(() => {
    // Reset API client token
    apiClient.setToken('test-token')
    
    // Clear any localStorage
    localStorage.clear()
    
    // Reset all mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Cleanup after each test
    vi.restoreAllMocks()
  })
}

/**
 * Wait for async operations (useful for testing async flows)
 */
export function wait(ms: number = 0): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Create a mock token for testing
 */
export function createTestToken(): string {
  return `test-token-${Date.now()}`
}

