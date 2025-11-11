// New message content types based on backend models
export interface TextMessageContent {
  type: "text";
  text: string;
  idx: number;
}

export interface ToolUseMessageContent {
  type: "tool_use";
  id: string;
  name: string;
  input: Record<string, any>;
  status: string;
  tool_call_pending_ts?: string;
  tool_call_confirmation_ts?: string;
  tool_call_execution_ts?: string;
  idx: number;
}

export interface ToolResultMessageContent {
  type: "tool_result";
  tool_use_id: string;
  content: string;
}

export type MessageContent = string | (TextMessageContent | ToolUseMessageContent | ToolResultMessageContent)[];

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'error' | 'rejected' | 'waiting_confirmation';
  result?: string;
  error?: string;
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  requires_confirmation?: boolean;
}

export interface ChatMessage {
  role: string; // "user", "assistant", "system", "tool_call"
  content: MessageContent; // Can be string or array of message content types
  timestamp?: string;
  message_id?: string;
  cost_info?: {
    input_tokens?: number;
    output_tokens?: number;
    cost_usd?: number;
  };
  // Remove tool_calls field - tool calls will be separate messages
  // tool_calls?: ToolCall[];
}

export interface ContextItem {
  context_type: string; // "mcp_server", "vmcp", or "agent"
  context_id: string;
  context_name: string;
  system_prompt?: string;
  tools: any[];
  resources: any[];
  prompts: any[];
  environment_variables: Record<string, string>;
}

export interface ToolMapping {
  tool_id: string;
  original_name: string;
  context_type: string;
  context_id: string;
  context_name: string;
  tool_schema: any;
}

export interface ConversationContext {
  context_items: ContextItem[];
  tool_mappings: Record<string, ToolMapping>;
  unified_tools: any[];
  unified_resources: any[];
  unified_prompts: any[];
  system_prompt?: string;
  websocket_user_id?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  model: string;
  created_at: string;
  updated_at: string;
  total_cost_usd?: number;
  total_tokens?: number;
  user_id?: string;
  system_prompt?: string;
  metadata?: Record<string, any>;
  context?: ConversationContext;
  llm_call_logs?: LLMCallLog[];
  primary_context?: {
    type: string;
    name: string;
    id: string;
    tools_count: number;
    resources_count: number;
    prompts_count: number;
  };
  context_summary?: {
    total_contexts: number;
    context_types: string[];
    total_tools: number;
    total_resources: number;
    total_prompts: number;
  };
}

export interface LLMCallLog {
  turn_id: string;
  conversation_id: string;
  created_at: string;
  model: string;
  provider: string;
  input_tokens?: number;
  output_tokens?: number;
  reasoning_tokens?: number;
  input_cost_usd?: number;
  output_cost_usd?: number;
  total_cost_usd?: number;
  total_cost_inr?: number;
  request_payload?: Record<string, any>;
  response_payload?: Record<string, any>;
  error?: string;
  duration_ms?: number;
  tool_calls?: Record<string, any>[];
  tool_results?: Record<string, any>[];
  tools_sent?: Record<string, any>[];
  system_prompt?: string;
}

export interface StreamEvent {
  event: string;
  data: any;
  timestamp: string;
  message_id?: string;
}

// New tool confirmation specific types
export interface ToolCallPendingEvent {
  event: 'tool_call_pending';
  data: {
    tool_name: string;
    tool_id: string;
    arguments: Record<string, any>;
    requires_confirmation: boolean;
  };
  timestamp: string;
  message_id?: string;
}

export interface ToolCallStartEvent {
  event: 'tool_call_start';
  data: {
    tool_name: string;
    tool_id: string;
    arguments: Record<string, any>;
  };
  timestamp: string;
  message_id?: string;
}

export interface ToolResultEvent {
  event: 'tool_result';
  data: {
    tool_id: string;
    result: string;
    rejected?: boolean;
    error?: boolean;
  };
  timestamp: string;
  message_id?: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
  system_prompt?: string;
  tools?: any[];
  resources?: any[];
  prompts?: any[];
}

export interface ContextCreateRequest {
  context_items: Array<{ type: string; id: string }>;
  system_prompt?: string;
  model?: string;
}

export interface ConversationCreateRequest {
  title?: string;
  model: string;
  system_prompt?: string;
  context?: ContextCreateRequest;
}

export interface ConversationUpdateRequest {
  title?: string;
  model?: string;
  system_prompt?: string;
}

export interface ToolCallRequest {
  tool_id: string;
  arguments: Record<string, any>;
}

export interface ToolCallConfirmation {
  tool_id: string;
  approved: boolean;
  conversation_id: string;
}

export interface VMCPSwitchRequest {
  vmcp_name?: string;
}

export interface ChatTool {
  id: string;
  name: string;
  description: string;
  server: string;
  parameters: Record<string, any>;
  // Add context information for vMCP tools
  context_type?: string;
  context_id?: string;
  original_name?: string;
}

export interface ChatResource {
  id: string;
  name: string;
  description: string;
  server: string;
  type: string;
  // Add context information for vMCP resources
  context_type?: string;
  context_id?: string;
  original_name?: string;
}

export interface ChatPrompt {
  id: string;
  name: string;
  description: string;
  server: string;
  arguments: Record<string, any>;
  // Add context information for vMCP prompts
  context_type?: string;
  context_id?: string;
  original_name?: string;
  // Preserve the full meta object for vMCP prompts
  meta?: {
    original_name?: string;
    server?: string;
    vmcp_id?: string;
    type?: string;
    custom_prompt_id?: string;
    [key: string]: any;
  };
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  server: string;
  inputSchema?: Record<string, any>;
  outputSchema?: Record<string, any>;
  meta?: Record<string, any>;
}

export interface Resource {
  id: string;
  name: string;
  description: string;
  server: string;
  type: string;
}

export interface Prompt {
  id: string;
  name: string;
  description: string;
  text: string;
  variables: string[];
}

export interface VMCPInfo {
  id: string;
  name: string;
  description?: string;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
  selected_servers: string[];
  selected_tools: Record<string, Tool[]>;
  selected_resources: Record<string, Resource[]>;
  selected_prompts: Record<string, Prompt[]>;
  tags?: string[];
  is_default: boolean;
  total_tools: number;
  total_resources: number;
  total_prompts: number;
}

export interface ChatSettings {
  defaultModel: string;
  defaultTemperature: number;
  defaultMaxTokens: number;
  autoScroll: boolean;
  showCosts: boolean;
  showToolCalls: boolean;
}

export interface StreamingState {
  isStreaming: boolean;
  currentMessage: string;
  toolCalls: ToolCall[];
  costInfo?: {
    total_cost_usd: number;
    input_tokens: number;
    output_tokens: number;
    reasoning_tokens?: number;
  };
}

// nApp types
export interface NApp {
  id: string;
  name: string;
  description: string;
  tsx_code: string;
  demo_key?: string; // Optional key to identify demo components
  vmcp_id?: string; // Optional link to vMCP for API access
  vmcp?: VMCPInfo; // Populated vMCP data when linked
  created_at: string;
  updated_at: string;
  is_active: boolean;
  user_id: string;
}

export interface NAppFormData {
  name: string;
  description: string;
  tsx_code: string;
  vmcp_id?: string;
}

export interface MCPConnection {
  serverId: string;
  connectionId: string;
  isConnected: boolean;
  tools: any[];
  prompts: any[];
  resources: any[];
}

export interface NAppContextType {
  currentNApp: NApp | null;
  mcpConnections: MCPConnection[];
  isLoading: boolean;
  error: string | null;
  
  // Tool interactions
  callTool: (toolName: string, toolArguments?: any) => Promise<any>;
  
  // Prompt interactions
  usePrompt: (promptName: string, promptArguments?: any) => Promise<any>;
  
  // Resource interactions
  readResource: (resourceUri: string) => Promise<any>;
  
  // Get all tools/prompts across connections
  getAllTools: () => any[];
  getAllPrompts: () => any[];
  getAllResources: () => any[];
  
  // Theme utilities
  theme: 'light' | 'dark';
  isDark: boolean;
  toggleTheme: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
} 