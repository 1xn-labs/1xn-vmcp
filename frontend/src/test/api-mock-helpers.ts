/**
 * API Mock Helpers
 * 
 * Reusable mock helpers for API testing with Vitest.
 * Use these utilities to create consistent mock responses.
 */

import { vi } from 'vitest'
import type {
  McpServerInfo,
  McpToolCallResult,
  McpResourceContent,
  VmcpInfo,
} from '../api/generated/types.gen'

/**
 * Creates a mock MCP server info response
 */
export function createMockMCPServer(
  overrides?: Partial<McpServerInfo>
): McpServerInfo {
  return {
    id: 'server-123',
    name: 'Test MCP Server',
    description: 'A test MCP server',
    status: 'connected',
    transport_type: 'stdio',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    command: 'python',
    args: ['-m', 'test_server'],
    auto_connect: true,
    enabled: true,
    ...overrides,
  }
}

/**
 * Creates a mock tool call result
 */
export function createMockToolCallResult(
  overrides?: Partial<McpToolCallResult>
): McpToolCallResult {
  return {
    content: [
      {
        type: 'text',
        text: 'Tool execution result',
      },
    ],
    tool_name: 'test_tool',
    server: 'server-123',
    server_id: 'server-123',
    isError: false,
    ...overrides,
  }
}

/**
 * Creates a mock resource content
 */
export function createMockResourceContent(
  overrides?: Partial<McpResourceContent>
): McpResourceContent {
  return {
    uri: 'file:///test/resource.txt',
    contents: [
      {
        uri: 'file:///test/resource.txt',
        text: 'Resource content here',
        mimeType: 'text/plain',
      },
    ],
    server: 'server-123',
    server_id: 'server-123',
    ...overrides,
  }
}

/**
 * Creates a mock vMCP info
 */
export function createMockVMCP(overrides?: Partial<VmcpInfo>): VmcpInfo {
  // Extract system_prompt from overrides to handle it separately
  const { system_prompt, ...restOverrides } = overrides || {}
  
  return {
    id: 'vmcp-123',
    name: 'Test vMCP',
    description: 'A test vMCP',
    status: 'active',
    user_id: 'user-123',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    custom_prompts: [],
    custom_tools: [],
    custom_resources: [],
    environment_variables: [],
    system_prompt: system_prompt ?? null, // Explicitly set to null if not provided
    ...restOverrides,
  }
}

/**
 * Creates a mock fetch response
 */
export function createMockFetchResponse<T>(
  data: T,
  options?: {
    ok?: boolean
    status?: number
    statusText?: string
  }
): Response {
  return {
    ok: options?.ok ?? true,
    status: options?.status ?? 200,
    statusText: options?.statusText ?? 'OK',
    json: async () => data,
    text: async () => JSON.stringify(data),
    headers: new Headers(),
    redirected: false,
    type: 'default' as ResponseType,
    url: '',
    clone: vi.fn(),
    body: null,
    bodyUsed: false,
    arrayBuffer: vi.fn(),
    blob: vi.fn(),
    formData: vi.fn(),
    bytes: async () => new Uint8Array(),
  } as unknown as Response
}

