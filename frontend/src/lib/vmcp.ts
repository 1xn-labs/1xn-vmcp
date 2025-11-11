// utils/vmcp-utils.ts
import { CheckCircle, AlertTriangle, Lock, WifiOff, Server, MessageSquare, FolderOpen, Code, Container } from 'lucide-react';
import { ServerStatusDisplay, Variable } from '../types/vmcp';

// Helper function to extract variables from text (var(variable))
export const extractVariables = (text: string): string[] => {
  const variableRegex = /var\(([a-zA-Z_][a-zA-Z0-9_]*?)\)/g;
  const variables: string[] = [];
  let match;
  while ((match = variableRegex.exec(text)) !== null) {
    variables.push(match[1]);
  }
  return [...new Set(variables)]; // Remove duplicates
};

// Helper function to extract environment variables from text (env(VAR_NAME))
export const extractEnvironmentVariables = (text: string): string[] => {
  const envVarRegex = /env\(([A-Z_][A-Z0-9_]*?)\)/g;
  const envVars: string[] = [];
  let match;
  while ((match = envVarRegex.exec(text)) !== null) {
    envVars.push(match[1]);
  }
  return [...new Set(envVars)]; // Remove duplicates
};

// Helper function to extract query parameters from URL
export const extractQueryParams = (url: string): Array<{ name: string; description: string; required: boolean; type: string; defaultValue?: string }> => {
  const queryParams: Array<{ name: string; description: string; required: boolean; type: string; defaultValue?: string }> = [];
  
  try {
    const urlObj = new URL(url);
    const searchParams = urlObj.searchParams;
    
    searchParams.forEach((value, key) => {
      // Determine type based on value
      let type = 'string';
      let defaultValue = value;
      
      // Check for type indicators in the value
      if (value === '<string>') {
        type = 'string';
        defaultValue = '';
      } else if (value === '<long>' || value === '<number>') {
        type = 'number';
        defaultValue = '0';
      } else if (value === '<boolean>') {
        type = 'boolean';
        defaultValue = 'false';
      } else if (value === '<array>' || value.includes(',')) {
        type = 'array';
        defaultValue = '[]';
      } else if (!isNaN(Number(value)) && value !== '') {
        type = 'number';
        defaultValue = value;
      } else if (value === 'true' || value === 'false') {
        type = 'boolean';
        defaultValue = value;
      }
      
      queryParams.push({
        name: key,
        description: `Query parameter: ${key}${defaultValue ? ` (default: ${defaultValue})` : ''}`,
        required: false, // Query parameters are typically optional
        type,
        defaultValue
      });
    });
  } catch (e) {
    // If URL parsing fails, try to extract query parameters manually
    const queryString = url.split('?')[1];
    if (queryString) {
      const params = queryString.split('&');
      params.forEach(param => {
        const [key, value] = param.split('=');
        if (key) {
          let type = 'string';
          let defaultValue = value || '';
          
          // Check for type indicators
          if (value === '<string>') {
            type = 'string';
            defaultValue = '';
          } else if (value === '<long>' || value === '<number>') {
            type = 'number';
            defaultValue = '0';
          } else if (value === '<boolean>') {
            type = 'boolean';
            defaultValue = 'false';
          } else if (value === '<array>') {
            type = 'array';
            defaultValue = '[]';
          } else if (!isNaN(Number(value)) && value !== '') {
            type = 'number';
            defaultValue = value;
          } else if (value === 'true' || value === 'false') {
            type = 'boolean';
            defaultValue = value;
          }
          
          queryParams.push({
            name: key,
            description: `Query parameter: ${key}${defaultValue ? ` (default: ${defaultValue})` : ''}`,
            required: false,
            type,
            defaultValue
          });
        }
      });
    }
  }
  
  return queryParams;
};

// Helper function to extract environment variables from text but only return those that exist in config
export const extractEnvironmentVariablesFromConfig = (text: string, configEnvVars: Array<{ name: string; value: string; description: string; required: boolean; source: string }>): string[] => {
  const allEnvVars = extractEnvironmentVariables(text);
  const configEnvVarNames = configEnvVars.map(env => env.name);
  return allEnvVars.filter(envVar => configEnvVarNames.includes(envVar));
};

// Helper function to rename environment variable across all content
export const renameEnvironmentVariable = (
  oldName: string, 
  newName: string, 
  vmcpConfig: any
): any => {
  const updatedConfig = { ...vmcpConfig };
  
  // Update system prompt
  if (updatedConfig.system_prompt?.text) {
    updatedConfig.system_prompt.text = updatedConfig.system_prompt.text.replace(
      new RegExp(`env\\(${oldName}\\)`, 'g'), 
      `env(${newName})`
    );
  }
  
  // Update custom prompts
  if (updatedConfig.custom_prompts) {
    updatedConfig.custom_prompts = updatedConfig.custom_prompts.map((prompt: any) => ({
      ...prompt,
      text: prompt.text.replace(
        new RegExp(`env\\(${oldName}\\)`, 'g'), 
        `env(${newName})`
      )
    }));
  }
  
  // Update custom tools
  if (updatedConfig.custom_tools) {
    updatedConfig.custom_tools = updatedConfig.custom_tools.map((tool: any) => ({
      ...tool,
      text: tool.text.replace(
        new RegExp(`env\\(${oldName}\\)`, 'g'), 
        `env(${newName})`
      )
    }));
  }
  
  // Update environment variables list
  if (updatedConfig.environment_variables) {
    updatedConfig.environment_variables = updatedConfig.environment_variables.map((env: any) => 
      env.name === oldName ? { ...env, name: newName } : env
    );
  }
  
  return updatedConfig;
};

// Helper function to extract tool calls from text (@server:tool_name(args) or @tool_name(args))
export const extractToolCalls = (
  text: string, 
  availableTools: any[] = [],
  selectedTools?: Record<string, string[]>
): Array<{
  server: string;
  tool_name: string;
  arguments_dict: Record<string, any>;
  inserted_string: string;
}> => {
  console.log('extractToolCalls - Input text:', text);
  console.log('extractToolCalls - Available tools count:', availableTools.length);
  
  const toolCallRegex = /@([a-zA-Z_][a-zA-Z0-9_]*):([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)|@([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)/g;
  const toolCalls: Array<{
    server: string;
    tool_name: string;
    arguments_dict: Record<string, any>;
    inserted_string: string;
  }> = [];

  let match;
  while ((match = toolCallRegex.exec(text)) !== null) {
    console.log('Processing match:', match);
    
    let toolName: string;
    let serverName: string;
    let argsString: string;
    const insertedString = match[0];

    if (match[1] && match[2]) {
      // New format: @server:tool_name(args)
      console.log('Using NEW format');
      serverName = match[1];
      toolName = match[2];
      argsString = match[3] || '';
    } else if (match[4] && match[5]) {
      // Old format: @tool_name(args)
      console.log('Using OLD format');
      toolName = match[4];
      argsString = match[5] || '';
      serverName = '';

      // Try to find server from available tools
      if (availableTools.length > 0) {
        const toolInfo = availableTools.find(tool => tool.name === toolName);
        if (toolInfo && toolInfo.server) {
          serverName = toolInfo.server;
        }
      }

      // Fallback to selected_tools mapping if not found in available tools
      if (!serverName && selectedTools) {
        for (const [serverNameKey, tools] of Object.entries(selectedTools)) {
          if (Array.isArray(tools) && tools.includes(toolName)) {
            serverName = serverNameKey;
            break;
          }
        }
      }
    } else {
      continue;
    }

    // Parse arguments
    const argumentsDict: Record<string, any> = {};
    if (argsString.trim()) {
      const argPairs = argsString.split(',').map(pair => pair.trim());
      argPairs.forEach(pair => {
        const [key, value] = pair.split('=').map(s => s.trim());
        if (key && value) {
          const cleanValue = value.replace(/^["']|["']$/g, '');
          argumentsDict[key] = cleanValue;
        }
      });
    }

    toolCalls.push({
      server: serverName,
      tool_name: toolName,
      arguments_dict: argumentsDict,
      inserted_string: insertedString
    });

    console.log(`Extracted tool call: ${toolName} from server: ${serverName}`, {
      toolName,
      serverName,
      argumentsDict,
      insertedString
    });
  }

  return toolCalls;
};

// Function to get status display similar to servers page
export const getStatusDisplay = (server: any): ServerStatusDisplay => {
  const currentStatus = server?.status || 'disconnected';

  switch (currentStatus) {
    case 'connected':
      return {
        label: 'Connected',
        color: 'bg-green-500/20 border-green-500/30 text-green-400',
        icon: CheckCircle,
        bgColor: 'bg-green-500/10'
      };
    case 'auth_required':
      return {
        label: 'Auth Required',
        color: 'bg-amber-500/20 border-amber-500/30 text-amber-400',
        icon: Lock,
        bgColor: 'bg-amber-500/10'
      };
    case 'error':
      return {
        label: 'Error',
        color: 'bg-red-500/20 border-red-500/30 text-red-400',
        icon: AlertTriangle,
        bgColor: 'bg-red-500/10'
      };
    default:
      return {
        label: 'Disconnected',
        color: 'bg-gray-500/20 border-gray-500/30 text-gray-400',
        icon: WifiOff,
        bgColor: 'bg-gray-500/10'
      };
  }
};

// Python function type extraction interface
export interface PythonFunctionInfo {
  name: string;
  parameters: Variable[];
  returnType?: string;
  docstring?: string;
}

export const PromptIcon = MessageSquare;
export const ToolIcon = Code;
export const McpIcon = Server;
export const VmcpIcon = Container;
export const ResourceIcon = FolderOpen;

// Convert Python type to display name
export const getTypeDisplayName = (type: string): string => {
  const displayNames: Record<string, string> = {
    'str': 'String',
    'int': 'Integer',
    'float': 'Float',
    'bool': 'Boolean',
    'list': 'List',
    'dict': 'Dictionary',
  };
  
  return displayNames[type] || 'String';
};

// Call backend API to extract Python function types
export const parsePythonFunction = async (code: string): Promise<PythonFunctionInfo[]> => {
  try {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      throw new Error('No access token available');
    }

    const response = await fetch('/api/vmcps/parse-python-function', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      throw new Error(`Failed to parse Python function: ${response.statusText}`);
    }

    const data = await response.json();
    return data.functions || [];
  } catch (error) {
    console.error('Error parsing Python function:', error);
    return [];
  }
};

// Validate value against type
export const validateValueByType = (value: any, type: string): { isValid: boolean; convertedValue?: any; error?: string } => {
  try {
    switch (type) {
      case 'str':
        return { isValid: true, convertedValue: String(value) };
      
      case 'int':
        const intValue = parseInt(String(value), 10);
        if (isNaN(intValue)) {
          return { isValid: false, error: `"${value}" is not a valid integer` };
        }
        return { isValid: true, convertedValue: intValue };
      
      case 'float':
        const floatValue = parseFloat(String(value));
        if (isNaN(floatValue)) {
          return { isValid: false, error: `"${value}" is not a valid float` };
        }
        return { isValid: true, convertedValue: floatValue };
      
      case 'bool':
        if (typeof value === 'boolean') {
          return { isValid: true, convertedValue: value };
        }
        const strValue = String(value).toLowerCase();
        if (['true', '1', 'yes', 'on'].includes(strValue)) {
          return { isValid: true, convertedValue: true };
        }
        if (['false', '0', 'no', 'off'].includes(strValue)) {
          return { isValid: true, convertedValue: false };
        }
        return { isValid: false, error: `"${value}" is not a valid boolean` };
      
      case 'list':
        if (Array.isArray(value)) {
          return { isValid: true, convertedValue: value };
        }
        try {
          const parsed = JSON.parse(String(value));
          if (Array.isArray(parsed)) {
            return { isValid: true, convertedValue: parsed };
          }
        } catch {
          // Fall through to error
        }
        return { isValid: false, error: `"${value}" is not a valid list` };
      
      case 'dict':
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          return { isValid: true, convertedValue: value };
        }
        try {
          const parsed = JSON.parse(String(value));
          if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
            return { isValid: true, convertedValue: parsed };
          }
        } catch {
          // Fall through to error
        }
        return { isValid: false, error: `"${value}" is not a valid dictionary` };
      
      default:
        return { isValid: true, convertedValue: String(value) };
    }
  } catch (error) {
    return { isValid: false, error: `Error validating value: ${error}` };
  }
};