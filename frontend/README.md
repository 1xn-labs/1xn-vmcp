# vMCP Frontend

React frontend application for managing vMCP (Virtual Model Context Protocol) servers and configurations. Provides a web interface for creating, managing, and using virtual MCPs that aggregate multiple MCP servers.

## Overview

The vMCP frontend is a modern React application built with:

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI component library (built on Radix UI)
- **Monaco Editor** - Code editor for tool configuration

The frontend communicates with the vMCP backend API to manage MCP servers, create virtual MCPs, and configure custom tools, resources, and prompts.

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client (auto-generated from OpenAPI + wrapper)
│   ├── components/       # React components
│   │   ├── auth/         # Authentication components
│   │   ├── layout/       # Layout components (sidebar, main layout)
│   │   ├── ui/           # shadcn/ui components
│   │   ├── vmcp/         # vMCP-specific components
│   │   └── ...
│   ├── contexts/         # React Context providers (theme, auth, vmcp, etc.)
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utilities and helpers
│   ├── pages/            # Page components (routes)
│   ├── styles/           # Global styles (Tailwind CSS)
│   └── types/            # TypeScript type definitions
├── public/               # Static assets
├── dist/                 # Build output
└── ...
```

### Key Directories

- **`src/api/`** - API client layer with auto-generated types from backend OpenAPI spec
- **`src/components/`** - Reusable React components organized by feature
- **`src/contexts/`** - Global state management using React Context
- **`src/pages/`** - Page-level components that correspond to routes
- **`src/hooks/`** - Custom hooks for shared logic
- **`src/lib/`** - Utility functions and helpers

## Getting Started

### Prerequisites

- Node.js (v18 or higher recommended)
- npm, yarn, pnpm, or bun

### Installation

```bash
# Install dependencies
npm install
```

### Environment Variables

Create a `.env` file in the frontend directory:

```bash
# Enable OSS mode (bypasses authentication for local development)
VITE_VMCP_OSS_BUILD=true

# Backend URL for API calls
VITE_BACKEND_URL=http://localhost:8000/
```

### Running the Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:3000`.

### OSS Mode

When `VITE_VMCP_OSS_BUILD=true` is set:
- Authentication is bypassed (no login required)
- API calls use 'local-token' for authentication
- Login/Register UI is hidden
- Direct access to all routes

## Development

### Available Scripts

- **`npm run dev`** - Start development server with hot reload
- **`npm run build`** - Build for production (outputs to `dist/`)
- **`npm run preview`** - Preview production build locally
- **`npm run lint`** - Run ESLint to check code quality
- **`npm run test`** - Run tests in watch mode
- **`npm run test:run`** - Run tests once (for CI)
- **`npm run generate:api`** - Generate API client from backend OpenAPI spec

### Path Aliases

The project uses path aliases for cleaner imports:
- `@/` maps to `src/`

Example:
```typescript
import { apiClient } from '@/api/client';
import { Button } from '@/components/ui/button';
```

### Development Workflow

1. Start the backend server (see backend README)
2. Start the frontend dev server: `npm run dev`
3. Make changes - hot reload will update automatically
4. Run linting: `npm run lint`
5. Run tests: `npm run test`

## API Client

The API client is automatically generated from the backend's OpenAPI specification, ensuring type safety between frontend and backend.

### Generating the API Client

```bash
# Make sure backend is running at http://localhost:8000
npm run generate:api
```

This command:
1. Fetches the OpenAPI spec from the backend
2. Generates TypeScript types and SDK functions
3. Outputs to `src/api/generated/`

### Usage

```typescript
import { apiClient } from '@/api/client';

// List MCP servers
const result = await apiClient.listMCPServers();
if (result.success) {
  console.log('Servers:', result.data);
}

// Create a vMCP
const createResult = await apiClient.createVMCP({
  name: 'My vMCP',
  description: 'Test vMCP',
  vmcp_config: { /* ... */ }
});
```

For detailed API client documentation, see [`src/api/README.md`](src/api/README.md).

## Routing

The application uses React Router with a basename of `/app` (matching the backend's frontend serving path).

### Route Structure

**Public Routes:**
- `/login` - Login page
- `/oauth/authorize` - OAuth authorization
- `/oauth/callback/success` - OAuth success callback
- `/oauth/callback/mcp` - OAuth MCP callback
- `/oauth_setup/:vmcp_name/configure` - OAuth setup configuration
- `/oauth_setup/:vmcp_name/callback` - OAuth setup callback

**Protected Routes** (require authentication via `AuthGuard`):
- `/vmcp` - vMCP list page
- `/vmcp/:id` - vMCP details page
- `/vmcp/install/:vmcp_id/:vmcp_type` - Install vMCP from collection
- `/vmcp/share/:vmcp_id` - Share vMCP page
- `/servers` - MCP servers management
- `/servers/add` - Add new MCP server
- `/servers/:name/edit` - Edit MCP server
- `/servers/:name/:id/test` - Test MCP server
- `/discover` - Discover MCP servers
- `/stats` - Usage statistics
- `/settings` - Settings page

### Route Protection

Routes are protected using the `AuthGuard` component, which:
- Checks authentication status
- Redirects to `/login` if not authenticated
- Allows access to public routes without authentication
- In OSS mode, bypasses authentication checks

### Lazy Loading

All page components are lazy-loaded for better performance:

```typescript
const VMCPListPage = lazy(() => import('@/pages/VMCPListPage'));
```

This reduces the initial bundle size and improves load times.

## Architecture

### Context Provider Hierarchy

The application uses React Context for global state management with a hierarchical provider structure:

```
ThemeProvider
  └── AuthProvider
      └── (Other providers as needed)
```

This ensures proper dependency order and prevents unnecessary re-renders.

### Component Structure

Components are organized by feature:
- **`components/auth/`** - Authentication-related components
- **`components/layout/`** - Layout components (sidebar, main layout)
- **`components/ui/`** - Reusable UI components (shadcn/ui)
- **`components/vmcp/`** - vMCP-specific components

### State Management

State is managed using React Context providers:
- **ThemeContext** - Theme (light/dark mode)
- **AuthContext** - Authentication state
- **VMCPContext** - vMCP data and operations
- **ServersContext** - MCP server data

For detailed architecture documentation, see [`ARCHITECTURE.md`](ARCHITECTURE.md).
