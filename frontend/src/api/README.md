# API Client Documentation

## Overview

The frontend API client has been regenerated from the backend's OpenAPI specification to ensure type safety and consistency between frontend and backend.

## Structure

```
src/lib/
├── generated-api/           # Auto-generated from OpenAPI spec
│   ├── core/               # Core HTTP client logic
│   ├── models/             # TypeScript interfaces for all API types
│   ├── services/           # Service classes for each API group
│   └── index.ts            # Main export file
├── new-api-v2.ts           # Wrapper around generated API (NEW)
├── new-api.ts              # Legacy API client (DEPRECATED)
└── API_CLIENT_README.md    # This file
```

## How It Works

### 1. Auto-Generation from OpenAPI Spec

The API client is automatically generated from the backend's OpenAPI specification using `@hey-api/openapi-ts`:

```bash
# Generate the API client (backend must be running at http://0.0.0.0:8080)
npm run generate:api

# Or manually:
npx openapi-ts -i http://0.0.0.0:8080/openapi.json -o ./src/api/generated
```

### 2. Wrapper Layer (client.ts)

The `client.ts` file provides:
- **Backward compatibility** with existing code
- **Consistent error handling** (returns `{ success, data, error }`)
- **OSS build authentication** handling
- **Token management** integration

## Usage

### Basic Usage

```typescript
import { apiClient } from '@/api/client';

// List MCP servers
const result = await apiClient.listMCPServers();
if (result.success) {
  console.log('Servers:', result.data);
} else {
  console.error('Error:', result.error);
}

// Create a vMCP
const createResult = await apiClient.createVMCP({
  name: 'My vMCP',
  description: 'Test vMCP',
  vmcp_config: { /* ... */ }
});
```

### Token Management

```typescript
import { apiClient, updateApiToken } from '@/api/client';

// Update authentication token
updateApiToken('your-access-token');

// Or set it directly
apiClient.setToken('your-access-token');
```

### OSS Build (No Auth)

In OSS build mode (`VITE_VMCP_OSS_BUILD=true`), the client automatically uses `local-token`:

```typescript
// Automatically configured in client.ts
const authDisabled = import.meta.env.VITE_VMCP_OSS_BUILD === 'true';
if (authDisabled) {
  apiClient.setToken('local-token'); // Backend recognizes this for no-auth mode
}
```

## Regenerating the API Client

When the backend API changes, regenerate the client:

### Prerequisites

Make sure your backend is running at `http://0.0.0.0:8080` (or update the URL in package.json script)

### Generate the Client

```bash
cd frontend
npm run generate:api
```

This will:
1. Fetch the OpenAPI spec from `http://0.0.0.0:8080/openapi.json`
2. Generate TypeScript types in `./src/api/generated/types.gen.ts`
3. Generate SDK functions in `./src/api/generated/sdk.gen.ts`
4. Generate client configuration in `./src/api/generated/client.gen.ts`

### Update Wrapper (if needed)

Check `client.ts` for any new methods that need to be exposed in the wrapper.

## Available Services

### McPsService (MCP Servers)

- `healthCheckApiMcpsHealthGet()` - Health check
- `installMcpServerApiMcpsInstallPost()` - Install MCP server
- `listServersApiMcpsListGet()` - List all servers
- `getServerInfoApiMcpsServerIdInfoGet()` - Get server info
- `connectServerApiMcpsServerIdConnectPost()` - Connect to server
- `disconnectServerApiMcpsServerIdDisconnectPost()` - Disconnect from server
- `uninstallServerApiMcpsServerIdUninstallDelete()` - Uninstall server
- `updateServerApiMcpsServerIdUpdatePut()` - Update server config
- `callToolApiMcpsServerIdToolsCallPost()` - Call MCP tool
- `readResourceApiMcpsServerIdResourcesReadPost()` - Read MCP resource
- `getPromptApiMcpsServerIdPromptsGetPost()` - Get MCP prompt
- `listToolsApiMcpsServerIdToolsListGet()` - List server tools
- `listResourcesApiMcpsServerIdResourcesListGet()` - List server resources
- `listPromptsApiMcpsServerIdPromptsListGet()` - List server prompts
- `discoverCapabilitiesApiMcpsServerIdDiscoverCapabilitiesPost()` - Discover capabilities

### VMcPsService (Virtual MCPs)

- `healthCheckApiVmcpsHealthGet()` - Health check
- `createVmcpApiVmcpsCreatePost()` - Create vMCP
- `listVmcpsApiVmcpsListGet()` - List all vMCPs
- `getVmcpApiVmcpsVmcpIdGet()` - Get vMCP details
- `updateVmcpApiVmcpsVmcpIdPut()` - Update vMCP
- `deleteVmcpApiVmcpsVmcpIdDelete()` - Delete vMCP
- `callToolApiVmcpsVmcpIdToolsCallPost()` - Call vMCP tool
- `readResourceApiVmcpsVmcpIdResourcesReadPost()` - Read vMCP resource
- `listToolsApiVmcpsVmcpIdToolsListGet()` - List vMCP tools
- `listResourcesApiVmcpsVmcpIdResourcesListGet()` - List vMCP resources
- `listPromptsApiVmcpsVmcpIdPromptsListGet()` - List vMCP prompts
- `refreshVmcpApiVmcpsVmcpIdRefreshPost()` - Refresh vMCP
- `getVmcpSummaryApiVmcpsVmcpIdSummaryGet()` - Get vMCP summary

## Type Safety

All types are automatically generated and exported from the `generated` directory:

```typescript
import type {
  MCPInstallRequest,
  MCPServerInfo,
  CreateVMCPRequest,
  VMCPResponse,
} from '@/api/client';

// Type-safe API calls
const createRequest: CreateVMCPRequest = {
  name: 'test',
  description: 'test vmcp',
  vmcp_config: {}
};

const result = await apiClient.createVMCP(createRequest);
// result.data is typed as VMCPCreateResponse
```

## Error Handling

All wrapper methods return a consistent response format:

```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;        // Present when success=true
  error?: string;  // Present when success=false
}
```

Example:

```typescript
const result = await apiClient.createVMCP(request);

if (result.success && result.data) {
  // TypeScript knows result.data exists and is VMCPCreateResponse
  console.log('Created vMCP:', result.data.vMCP);
} else if (result.error) {
  // TypeScript knows result.error exists and is string
  console.error('Failed to create vMCP:', result.error);
}
```

## Best Practices

1. **Always use the wrapper** (`client.ts`) instead of calling generated SDK functions directly
2. **Check `success` field** before accessing `data`
3. **Set token once** at app initialization, not per request
4. **Regenerate client** after backend API changes
5. **Use TypeScript** to catch type mismatches at compile time
6. **Keep backend running** when regenerating the API client

## Troubleshooting

### "No access token available" error

Make sure the token is set:

```typescript
import { updateApiToken } from '@/api/client';

// After login
const token = localStorage.getItem('access_token');
if (token) {
  updateApiToken(token);
}
```

### Type errors after backend changes

Regenerate the API client to sync with backend schema:

```bash
npm run generate:api
```

### OSS build not working

Verify environment variable is set:

```bash
# .env.development
VITE_VMCP_OSS_BUILD=true
```

## Future Enhancements

- [ ] Add request/response interceptors
- [ ] Add retry logic for failed requests
- [ ] Add request caching layer
- [ ] Add WebSocket support for streaming
- [ ] Generate API client as part of CI/CD pipeline
