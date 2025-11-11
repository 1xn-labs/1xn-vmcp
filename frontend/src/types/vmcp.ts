// types/vmcp.ts
export interface Resource {
  id: string;
  original_filename: string;
  size: number;
  content_type?: string;
  created_at?: string;
  filename?: string;
  resource_name?: string;
  user_id?: string;
  vmcp_id?: string;
}

export interface MCPServer {
  name: string;
  server_id: string;
  transport_type: string;
  command?: string;
  url?: string;
  favicon_url?: string;
  description?: string;
}

export interface MCPRegistryConfig {
  name: string;
  transport_type: string;
  description?: string;
  server_id?: string;
  favicon_url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
}

export interface VMCPSelectedServer extends MCPServer {
  status?: string;
  last_connected?: string | null;
  last_error?: string | null;
  capabilities?: {
    tools_count?: number;
    resources_count?: number;
    prompts_count?: number;
  };
  tool_details?: any[];
  resource_details?: any[];
  prompt_details?: any[];
  resource_template_details?: any[];
  auto_connect?: boolean;
  enabled?: boolean;
}

export interface Variable {
  name: string;
  description: string;
  required: boolean;
  type?: string; // Data type: 'str', 'int', 'float', 'bool', 'list', 'dict', etc.
}

export interface EnvironmentVariable {
  name: string;
  description: string;
  required: boolean;
}

export interface EnvironmentVariableConfig {
  name: string;
  value: string;
  description: string;
  required: boolean;
  source: string;
}

export interface ToolCall {
  server: string;
  tool_name: string;
  arguments_dict: Record<string, any>;
  inserted_string: string;
}

export interface ResourceTemplate {
  id: string;
  name: string;
  description: string;
  template: string;
}
export interface Prompt {
      name: string;
      description: string;
      text: string;
      variables: Array<Variable>;
      environment_variables: Array<EnvironmentVariable>;
      tool_calls: Array<ToolCall>;
      atomic_blocks?: Array<{
        id: string;
        startLine: number;
        startColumn: number;
        endLine: number;
        endColumn: number;
        type: 'tool' | 'prompt' | 'resource' | 'env' | 'var';
        server: string;
        name: string;
        text: string;
        data: any;
        parameters: Record<string, any>;
      }>;
    }

export interface Tool {
    name: string;
    description: string;
    text: string;
    variables: Array<Variable>;
    environment_variables: Array<EnvironmentVariable>;
    tool_calls: Array<ToolCall>;
    keywords?: string[];
    tool_type?: 'prompt' | 'python' | 'http';
    // Python tool specific fields
    code?: string;
    imports?: string[];
    dependencies?: string[];
    // HTTP tool specific fields
    api_config?: {
      method: string;
      url: string;
      headers: Record<string, string>;
      headers_array?: Array<{ key: string; value: string }>;
      body: any;
      body_parsed?: any;
      query_params: Record<string, string>;
      auth?: {
        type: 'none' | 'bearer' | 'apikey' | 'basic';
        token?: string;
        apiKey?: string;
        username?: string;
        password?: string;
      };
    };
    imported_from?: 'postman' | 'openapi' | null;
    atomic_blocks?: Array<{
      id: string;
      startLine: number;
      startColumn: number;
      endLine: number;
      endColumn: number;
      type: 'tool' | 'prompt' | 'resource' | 'env' | 'var';
      server: string;
      name: string;
      text: string;
      data: any;
      parameters: Record<string, any>;
    }>;
  }

export interface PublicVMCPInfo {
    creator_id: string;
    creator_username: string;
    install_count: number;
    rating: number | null;
    rating_count: number;
}

export interface VMCPConfig {
    id: string;
    name: string;
    user_id: string;
    description: string;
    system_prompt: {
      text: string;
      variables: Array<Variable>;
      environment_variables: Array<EnvironmentVariable>;
      tool_calls: Array<ToolCall>;
    };
    vmcp_config: {
      name: string;
      description: string;
      enabled: boolean;
      selected_servers: Array<VMCPSelectedServer>;
      selected_tools: Record<string, string[]>;
      selected_resources: Record<string, string[]>;
      selected_prompts: Record<string, string[]>;
      selected_tool_overrides: Record<string, Record<string, { name: string; description: string; originalName: string; originalDescription: string }>>;
      tags: string[];
      is_default: boolean;
    };
    custom_prompts: Array<Prompt>;
    custom_tools: Array<Tool>;
    custom_context: string[];
    custom_resources: Array<Resource>;
    custom_resource_templates: Array<ResourceTemplate>;
    custom_resource_uris: string[];
    environment_variables: Array<EnvironmentVariableConfig>;
    uploaded_files: Array<Resource>;
    created_at: string;
    updated_at: string;
    created_by: string;
    total_tools: number;
    total_resources: number;
    total_resource_templates: number;
    total_prompts: number;
    is_public: boolean;
    public_info: PublicVMCPInfo;
    public_tags: string[];
    public_at: string;
    is_wellknown: boolean;
    metadata: any;
}

export interface VMCPRegistryConfig {
    id: string;
    name: string;
    user_id: string;
    description?: string;
    vmcp_config?: {
      selected_servers: Array<MCPRegistryConfig>;
      [key: string]: any;
    };
    environment_variables: Array<Record<string, any>>;
    created_at?: string;
    updated_at?: string;
    creator_id?: string;
    creator_username?: string;
    total_tools?: number;
    total_resources?: number;
    total_resource_templates?: number;
    total_prompts?: number;
    public_info?: PublicVMCPInfo;
    is_public: boolean;
    public_tags: string[];
    public_at?: string;
    is_wellknown: boolean;
    metadata?: any;
}

export interface ServerStatusDisplay {
  label: string;
  color: string;
  icon: any;
  bgColor: string;
}