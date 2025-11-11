/**
 * Integration Test Suite 5: Custom Tools - Python Type
 * Tests for Python-based custom tools with REAL API calls
 * 
 * Requires: Backend server running on localhost:8000
 * 
 * Corresponds to: backend/tests/test_05_custom_tools_python.py
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

setupIntegrationTests()

describe('Integration Test Suite 5: Custom Tools - Python Type', () => {
  let createdVMCP: Awaited<ReturnType<typeof createVMCPForTest>>

  beforeAll(async () => {
    await requireBackend()
    createdVMCP = await createVMCPForTest(generateVMCPName())
  })

  describe('Test 5.1: Create a simple Python tool', () => {
    it('should create a simple Python tool', async () => {
      console.log(`\n📦 Test 5.1 - Creating simple Python tool: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'add_numbers',
            description: 'Add two numbers',
            tool_type: 'python',
            code: `def main(a: int, b: int):
    return a + b
`,
            variables: [
              { name: 'a', description: 'First number', type: 'int', required: true },
              { name: 'b', description: 'Second number', type: 'int', required: true },
            ],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      const result = await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      expect(result.success).toBe(true)
      expect(result.data?.custom_tools?.length).toBe(1)
      expect(result.data?.custom_tools?.[0]?.tool_type).toBe('python')

      console.log('✅ Simple Python tool created successfully')
    })
  })

  describe('Test 5.2: Call a simple Python tool', () => {
    it('should call a simple Python tool', async () => {
      console.log(`\n📦 Test 5.2 - Calling simple Python tool: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'multiply',
            description: 'Multiply two numbers',
            tool_type: 'python',
            code: `def main(x: int, y: int):
    result = x * y
    return f"Result: {result}"
`,
            variables: [
              { name: 'x', description: 'First number', type: 'int', required: true },
              { name: 'y', description: 'Second number', type: 'int', required: true },
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
        tool_name: 'multiply',
        arguments: { x: 5, y: 7 },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toContain('35')
      }

      console.log('✅ Python tool call successful')
    })
  })

  describe('Test 5.3: Python tool with string type', () => {
    it('should call Python tool with string variables', async () => {
      console.log(`\n📦 Test 5.3 - Python tool with string variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'string_formatter',
            description: 'Format strings',
            tool_type: 'python',
            code: `def main(first_name, last_name):
    full_name = f"{first_name} {last_name}"
    return full_name.upper()
`,
            variables: [
              { name: 'first_name', description: 'First name', type: 'str', required: true },
              { name: 'last_name', description: 'Last name', type: 'str', required: true },
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
        tool_name: 'string_formatter',
        arguments: { first_name: 'John', last_name: 'Doe' },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toContain('JOHN DOE')
      }

      console.log('✅ Python tool with strings successful')
    })
  })

  describe('Test 5.4: Python tool with list type', () => {
    it('should call Python tool with list variables', async () => {
      console.log(`\n📦 Test 5.4 - Python tool with list variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'sum_list',
            description: 'Sum a list of numbers',
            tool_type: 'python',
            code: `def main(numbers: list[int]):
    total = sum(numbers)
    return f"Sum: {total}"
`,
            variables: [
              { name: 'numbers', description: 'List of numbers', type: 'list', required: true },
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
        tool_name: 'sum_list',
        arguments: { numbers: [1, 2, 3, 4, 5] },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        expect(result.data.content[0].text).toContain('15')
      }

      console.log('✅ Python tool with list successful')
    })
  })

  describe('Test 5.5: Python tool with dict type', () => {
    it('should call Python tool with dict variables', async () => {
      console.log(`\n📦 Test 5.5 - Python tool with dict variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'process_data',
            description: 'Process dictionary data',
            tool_type: 'python',
            code: `def main(data: dict):
    keys = list(data.keys())
    return f"Keys: {', '.join(keys)}"
`,
            variables: [
              { name: 'data', description: 'Dictionary data', type: 'dict', required: true },
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
        tool_name: 'process_data',
        arguments: { data: { name: 'Alice', age: 30, city: 'NYC' } },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        const text = result.data.content[0].text
        expect(text).toContain('name')
        expect(text).toContain('age')
        expect(text).toContain('city')
      }

      console.log('✅ Python tool with dict successful')
    })
  })

  describe('Test 5.6: Python tool with float type', () => {
    it('should call Python tool with float variables', async () => {
      console.log(`\n📦 Test 5.6 - Python tool with float variables: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'calculate_area',
            description: 'Calculate circle area',
            tool_type: 'python',
            code: `def main(radius: float):
    import math
    area = math.pi * radius * radius
    return f"Area: {area:.2f}"
`,
            variables: [
              { name: 'radius', description: 'Circle radius', type: 'float', required: true },
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
        tool_name: 'calculate_area',
        arguments: { radius: 5.0 },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        // pi * 5^2 ≈ 78.54
        expect(result.data.content[0].text).toContain('78')
      }

      console.log('✅ Python tool with float successful')
    })
  })

  describe('Test 5.7: Python tool with default values', () => {
    it('should call Python tool with default values', async () => {
      console.log(`\n📦 Test 5.7 - Python tool with default values: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'greet_user',
            description: 'Greet user with optional title',
            tool_type: 'python',
            code: `def main(name, title="Mr/Ms"):
    return f"Hello {title} {name}!"
`,
            variables: [
              { name: 'name', description: "User's name", type: 'str', required: true },
              { name: 'title', description: "User's title", type: 'str', required: false, default_value: 'Mr/Ms' },
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
        tool_name: 'greet_user',
        arguments: { name: 'Smith' },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        const text = result.data.content[0].text
        expect(text).toContain('Smith')
      }

      console.log('✅ Python tool with default values successful')
    })
  })

  describe('Test 5.8: Python tool with complex logic', () => {
    it('should call Python tool with complex logic', async () => {
      console.log(`\n📦 Test 5.8 - Python tool with complex logic: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'fibonacci',
            description: 'Calculate Fibonacci number',
            tool_type: 'python',
            code: `def main(n: int):
    if n <= 0:
        return "Invalid input"
    elif n == 1:
        return 0
    elif n == 2:
        return 1
    else:
        a, b = 0, 1
        for _ in range(n - 2):
            a, b = b, a + b
        return b
`,
            variables: [
              { name: 'n', description: 'Position in Fibonacci sequence', type: 'int', required: true },
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
        tool_name: 'fibonacci',
        arguments: { n: 10 },
      })

      expect(result.success).toBe(true)
      if (result.data?.content?.[0]?.text) {
        // 10th Fibonacci number is 34
        expect(result.data.content[0].text).toContain('34')
      }

      console.log('✅ Python tool with complex logic successful')
    })
  })

  describe('Test 5.9: Python tool error handling', () => {
    it('should handle Python tool errors', async () => {
      console.log(`\n📦 Test 5.9 - Python tool error handling: ${createdVMCP.id}`)

      const vmcpData = await apiClient.getVMCPDetails(createdVMCP.id)
      if (!vmcpData.success || !vmcpData.data) {
        throw new Error('Failed to get vMCP data')
      }

      const updatedConfig = {
        id: createdVMCP.id,
        name: createdVMCP.name,
        custom_tools: [
          {
            name: 'divide',
            description: 'Divide two numbers',
            tool_type: 'python',
            code: `def main(numerator: float, denominator: float):
    if denominator == 0:
        raise ValueError("Cannot divide by zero")
    return numerator / denominator
`,
            variables: [
              { name: 'numerator', description: 'Numerator', type: 'float', required: true },
              { name: 'denominator', description: 'Denominator', type: 'float', required: true },
            ],
            environment_variables: [],
            tool_calls: [],
            atomic_blocks: [],
          },
        ],
      }

      await apiClient.updateVMCP(createdVMCP.id, updatedConfig)
      await wait(200)

      // Test valid division
      const resultValid = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'divide',
        arguments: { numerator: 10, denominator: 2 },
      })

      expect(resultValid.success).toBe(true)
      if (resultValid.data?.content?.[0]?.text) {
        expect(resultValid.data.content[0].text).toContain('5')
      }

      // Test division by zero
      const resultError = await apiClient.callVMCPTool(createdVMCP.id, {
        tool_name: 'divide',
        arguments: { numerator: 10, denominator: 0 },
      })

      // Should either succeed with error message or fail gracefully
      if (resultError.success && resultError.data?.content?.[0]?.text) {
        const errorText = resultError.data.content[0].text.toLowerCase()
        expect(errorText).toMatch(/error|zero/)
      }

      console.log('✅ Python tool error handling successful')
    })
  })
})

