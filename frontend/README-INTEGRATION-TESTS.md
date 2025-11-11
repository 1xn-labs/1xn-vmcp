# Frontend Integration Tests

Integration tests that make **real API calls** to a running backend server.

## Prerequisites

### Required Services

Before running integration tests, ensure all required services are running:

1. **vMCP Backend Server** (port 8000)
   ```bash
   cd backend
   python -m uvicorn src.vmcp.main:app --reload --port 8000
   ```

2. **MCP Test Servers** (port 8001)
   ```bash
   cd backend
   python -m mcp_server.start_mcp_servers
   ```
   This starts:
   - Everything MCP Server: `http://localhost:8001/everything/mcp`
   - AllFeature MCP Server: `http://localhost:8001/allfeature/mcp`

3. **Test HTTP Server** (port 8002) - Optional for HTTP tool tests
   ```bash
   cd backend
   python -m test_server.test_http_server
   ```

## Running Integration Tests

```bash
# Run all integration tests
npm run test:integration

# Run with UI
npm run test:integration:ui

# Run specific integration test file
npm run test:integration -- test_01_vmcp_creation.integration.test.ts
```

## Test Structure

Integration tests are located in `src/api/` with the `.integration.test.ts` suffix:

- `test_01_vmcp_creation.integration.test.ts` - Real vMCP CRUD operations
- `test_02_mcp_server_integration.integration.test.ts` - Real MCP server operations
- (More integration test files will be added)

## Differences from Unit Tests

| Feature | Unit Tests | Integration Tests |
|---------|-----------|-------------------|
| **API Calls** | Mocked | Real HTTP requests |
| **Backend Required** | ❌ No | ✅ Yes |
| **Speed** | Fast (< 1s) | Slower (5-30s) |
| **Isolation** | Complete | May affect each other |
| **Cleanup** | Automatic | Automatic (via fixtures) |
| **Coverage** | API client logic | Full stack |

## Automatic Cleanup

Integration tests automatically clean up created resources:

- **vMCPs** - Automatically deleted after all tests complete
- **MCP Servers** - Automatically uninstalled after all tests complete

Cleanup happens in the `afterAll` hook of `integration-setup.ts`.

## Health Checks

Integration tests check if the backend is available before running. If the backend is not running:

- Tests will fail with a helpful error message
- You'll be prompted to start the backend server

## Example Test

```typescript
describe('Integration Test Suite 1: vMCP Creation', () => {
  it('should create a vMCP with real API call', async () => {
    // This makes a REAL HTTP request to localhost:8000
    const result = await apiClient.createVMCP({
      name: 'test-vmcp',
      description: 'Test description'
    })
    
    expect(result.success).toBe(true)
    expect(result.data?.id).toBeDefined()
    
    // Cleanup is automatic
  })
})
```

## Troubleshooting

### Backend Not Running

```
Error: Backend server is not available at http://localhost:8000
```

**Solution**: Start the backend server (see Prerequisites)

### Port Already in Use

If port 8000 is already in use, either:
- Stop the existing process
- Or update `BASE_URL` in `src/test/test-setup.ts` to point to a different port

### Test Timeouts

Integration tests have a 30-second timeout. If tests timeout:
- Check backend server logs for errors
- Verify MCP test servers are running
- Increase timeout in `vitest.config.integration.ts` if needed

### Cleanup Failures

If cleanup fails, you may need to manually delete test resources:
```typescript
// In the browser console or a cleanup script
await apiClient.deleteVMCP('vmcp-id')
await apiClient.uninstallMCPServer('server-id')
```

