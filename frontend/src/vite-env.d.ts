/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string
  readonly VITE_VMCP_OSS_BUILD?: string
  readonly VITE_UNIFIED_BACKEND_URL?: string
  readonly VITE_MCP_SERVER_URL?: string
  readonly VITE_ENTITY_STRING?: string
  readonly VITE_BASE_PATH?: string
  readonly VITE_ASSET_PREFIX?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
