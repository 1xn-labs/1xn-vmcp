// components/ToolsTab.tsx

import { useState, useEffect } from 'react';
import { Plus, Trash2, Save, X, Edit, Play, Loader2, Braces, FolderInput, Code } from 'lucide-react';
import { ToolIcon, McpIcon, VmcpIcon, PromptIcon } from '@/lib/vmcp';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import VMCPMonacoEditor from '@/components/editor/VMCPMonacoEditor';
import { VMCPConfig } from '@/types/vmcp';
import { extractVariables, extractEnvironmentVariables, renameEnvironmentVariable, extractQueryParams, parsePythonFunction, getTypeDisplayName, validateValueByType } from '@/lib/vmcp';
import { cn } from '@/lib/utils';
// import { newApi, VMCPToolCallRequest } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import type { VmcpToolCallRequest as VMCPToolCallRequest } from '@/api/generated/types.gen';
import { useToast } from '@/hooks/use-toast';

import HttpToolImporter from '@/components/vmcp/HttpToolImporter';
import HttpTool from '@/components/vmcp/HttpToolImporter';
import { Separator } from '@/components/ui/separator';


// Function to create parsed body with @param placeholders
const createParsedBody = (obj: any, prefix: string = ''): any => {
  if (typeof obj === 'string') {
    // Check if it's a placeholder like <string>, <long>, etc.
    if (obj.match(/^<[^>]+>$/)) {
      const varName = prefix || 'param';
      return `@param.${varName}`;
    }
    // Check if it's a variable like {{VARIABLE}}
    else if (obj.includes('{{') && obj.includes('}}')) {
      const varMatch = obj.match(/\{\{([^}]+)\}\}/);
      if (varMatch) {
        return `@param.${varMatch[1]}`;
      }
    }
    return obj;
  } else if (Array.isArray(obj)) {
    return obj.map((item, index) => {
      if (typeof item === 'object' && item !== null) {
        return createParsedBody(item, `${prefix}_${index}`);
      } else if (typeof item === 'string' && item.match(/^<[^>]+>$/)) {
        return `@param.${prefix}_${index}`;
      }
      return item;
    });
  } else if (typeof obj === 'object' && obj !== null) {
    const result: any = {};
    Object.keys(obj).forEach(key => {
      const varName = prefix ? `${prefix}_${key}` : key;
      result[key] = createParsedBody(obj[key], varName);
    });
    return result;
  }
  return obj;
};

// Function to extract variables from JSON object and create parameters
const extractVariablesFromJson = (obj: any, prefix: string = ''): Array<{ name: string; description: string; required: boolean; type: string }> => {
  const variables: Array<{ name: string; description: string; required: boolean; type: string }> = [];

  const processValue = (value: any, key: string, currentPrefix: string) => {
    const varName = currentPrefix ? `${currentPrefix}_${key}` : key;

    if (typeof value === 'string') {
      // Check if it's a placeholder like <string>, <long>, etc.
      if (value.match(/^<[^>]+>$/)) {
        const type = value.replace(/[<>]/g, '').toLowerCase();
        variables.push({
          name: varName,
          description: `Body parameter: ${key} (default: ${value})`,
          required: true,
          type: type === 'long' ? 'number' : type === 'boolean' ? 'boolean' : 'string'
        });
      }
      // Check if it's a variable like {{VARIABLE}}
      else if (value.includes('{{') && value.includes('}}')) {
        const varMatch = value.match(/\{\{([^}]+)\}\}/);
        if (varMatch) {
          variables.push({
            name: varMatch[1],
            description: `Body variable: ${key}`,
            required: true,
            type: 'string'
          });
        }
      }
    } else if (Array.isArray(value)) {
      // Process array elements
      value.forEach((item, index) => {
        if (typeof item === 'object' && item !== null) {
          processValue(item, `${key}_${index}`, currentPrefix);
        } else if (typeof item === 'string' && item.match(/^<[^>]+>$/)) {
          const type = item.replace(/[<>]/g, '').toLowerCase();
          variables.push({
            name: `${varName}_${index}`,
            description: `Body parameter: ${key}[${index}] (default: ${item})`,
            required: true,
            type: type === 'long' ? 'number' : type === 'boolean' ? 'boolean' : 'string'
          });
        }
      });
    } else if (typeof value === 'object' && value !== null) {
      // Process nested objects
      Object.keys(value).forEach(nestedKey => {
        processValue(value[nestedKey], nestedKey, varName);
      });
    }
  };

  if (typeof obj === 'object' && obj !== null) {
    Object.keys(obj).forEach(key => {
      processValue(obj[key], key, prefix);
    });
  }

  return variables;
};

interface ToolsTabProps {
  vmcpConfig: VMCPConfig;
  servers: any[];
  // selectedToolsByServer: { [serverId: string]: Set<string> };
  // setSelectedToolsByServer: (tools: { [serverId: string]: Set<string> } | ((prev: { [serverId: string]: Set<string> }) => { [serverId: string]: Set<string> })) => void;
  expandedSections: Set<string>;
  setExpandedSections: (sections: Set<string> | ((prev: Set<string>) => Set<string>)) => void;
  addCustomTool: (toolType?: 'prompt' | 'python' | 'http') => void;
  removeCustomTool: (index: number) => void;
  // getAllTools: () => any[];
  // getAllResources: () => any[];
  setVmcpConfig: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
  isRemoteVMCP?: boolean;
  forceRefreshVMCPData?: () => Promise<void>;
}

export default function ToolsTab({
  vmcpConfig,
  servers,
  addCustomTool,
  removeCustomTool,
  setVmcpConfig,
  isRemoteVMCP = false,
  forceRefreshVMCPData,
}: ToolsTabProps) {
  const [toolViewMode, setToolViewMode] = useState<'list' | 'edit'>('list');
  const [selectedToolIndex, setSelectedToolIndex] = useState<number | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [modalName, setModalName] = useState('');
  const [modalValue, setModalValue] = useState('');
  const [modalDescription, setModalDescription] = useState('');
  const [modalRequired, setModalRequired] = useState(false);
  const [showVariableModal, setShowVariableModal] = useState(false);
  const [variableModalName, setVariableModalName] = useState('');
  const [variableModalDescription, setVariableModalDescription] = useState('');
  const [variableModalRequired, setVariableModalRequired] = useState(false);
  const [variableModalType, setVariableModalType] = useState<'add' | 'edit'>('add');
  const [variableModalDataType, setVariableModalDataType] = useState('str');
  const [editingVariableIndex, setEditingVariableIndex] = useState<number | null>(null);

  // Test tool states
  const [showTestToolModal, setShowTestToolModal] = useState(false);
  const [testToolLoading, setTestToolLoading] = useState(false);
  const [testToolResult, setTestToolResult] = useState<string | null>(null);
  const [testToolError, setTestToolError] = useState<string | null>(null);
  const [testToolParameters, setTestToolParameters] = useState<Record<string, any>>({});
  const [availableTools, setAvailableTools] = useState<any[]>([]);

  const { success, error } = useToast();


  // MCP Server test states
  const [mcpTestToolModal, setMcpTestToolModal] = useState<{
    isOpen: boolean;
    tool: any | null;
    serverId: string | null;
    formData: Record<string, any>;
    testing: boolean;
    result: string | null;
    error: string | null;
  }>({
    isOpen: false,
    tool: null,
    serverId: null,
    formData: {},
    testing: false,
    result: null,
    error: null,
  });

  // Tool override states (per-tool)
  const [showToolOverrideModal, setShowToolOverrideModal] = useState(false);
  const [overrideToolName, setOverrideToolName] = useState<string | null>(null);
  const [overrideServerId, setOverrideServerId] = useState<string | null>(null);
  const [overrideTool, setOverrideTool] = useState<any | null>(null);
  const [overrideNameValue, setOverrideNameValue] = useState('');
  const [overrideDescriptionValue, setOverrideDescriptionValue] = useState('');
  const [savingOverride, setSavingOverride] = useState(false);

  // HTTP tool importer states
  const [showHttpImporter, setShowHttpImporter] = useState(false);

  // Reset modal states when switching between tools
  useEffect(() => {
    if (selectedToolIndex !== null) {
      setShowVariableModal(false);
      setEditingIndex(null);
      setEditingVariableIndex(null);
    }
  }, [selectedToolIndex]);

  const handleAddNew = () => {
    console.log('Opening environment variable modal');
    setEditingIndex(null);
    setModalName('');
    setModalValue('');
    setModalDescription('');
    setModalRequired(false);
    setShowVariableModal(false); // Close variable modal if open
  };

  const handleEdit = (index: number) => {
    const envVar = vmcpConfig.environment_variables[index];
    setEditingIndex(index);
    setModalName(envVar.name);
    setModalValue(envVar.value);
    setModalDescription(envVar.description);
    setModalRequired(envVar.required);
  };

  const handleSave = () => {
    if (!modalName.trim()) return;

    if (editingIndex !== null) {
      // Editing existing variable
      const oldName = vmcpConfig.environment_variables[editingIndex].name;
      const newName = modalName.trim();

      if (newName !== oldName) {
        // Rename environment variable across all content
        setVmcpConfig(prev => renameEnvironmentVariable(oldName, newName, prev));
      }

      // Update the environment variable
      setVmcpConfig(prev => ({
        ...prev,
        environment_variables: prev.environment_variables.map((ev, i) =>
          i === editingIndex ? { ...ev, name: newName, value: modalValue, description: modalDescription, required: modalRequired } : ev
        )
      }));
    } else {
      // Adding new variable
      setVmcpConfig(prev => ({
        ...prev,
        environment_variables: [...prev.environment_variables, {
          name: modalName.trim(),
          value: modalValue,
          description: modalDescription,
          required: modalRequired,
          source: 'custom_tool'
        }]
      }));
    }

  };

  const handleCancel = () => {
    setEditingIndex(null);
    setModalName('');
    setModalValue('');
    setModalDescription('');
    setModalRequired(false);
  };

  const handleAddVariable = () => {
    console.log('Opening variable modal');
    setVariableModalType('add');
    setVariableModalName('');
    setVariableModalDescription('');
    setVariableModalRequired(false);
    setVariableModalDataType('str');
    setEditingVariableIndex(null);
    setShowVariableModal(true);
  };

  const handleEditVariable = (index: number) => {
    if (selectedToolIndex === null) return;

    const tool = vmcpConfig.custom_tools[selectedToolIndex];
    if (!tool.variables) tool.variables = [];

    const variable = tool.variables[index];
    setVariableModalType('edit');
    setVariableModalName(variable.name);
    setVariableModalDescription(variable.description || '');
    setVariableModalRequired(variable.required || false);
    setVariableModalDataType(variable.type || 'str');
    setEditingVariableIndex(index);
    setShowVariableModal(true);
  };

  const handleSaveVariable = () => {
    if (!variableModalName.trim() || selectedToolIndex === null) return;

    const tool = vmcpConfig.custom_tools[selectedToolIndex];
    if (!tool.variables) tool.variables = [];

    if (variableModalType === 'edit' && editingVariableIndex !== null) {
      // Editing existing variable
      const oldName = tool.variables[editingVariableIndex].name;
      const newName = variableModalName.trim();

      if (newName !== oldName) {
        // Rename variable in tool text
        const newText = tool.text.replace(new RegExp(`var\\(${oldName}\\)`, 'g'), `var(${newName})`);
        tool.text = newText;
      }

      // Update the variable
      tool.variables[editingVariableIndex] = {
        name: newName,
        description: variableModalDescription,
        required: variableModalRequired,
        type: variableModalDataType
      };
    } else {
      // Adding new variable
      tool.variables.push({
        name: variableModalName.trim(),
        description: variableModalDescription,
        required: variableModalRequired,
        type: variableModalDataType
      });

    }

    // Update the VMCP config
    setVmcpConfig(prev => ({
      ...prev,
      custom_tools: prev.custom_tools.map((t, i) =>
        i === selectedToolIndex ? tool : t
      )
    }));

    setShowVariableModal(false);
  };

  const handleCancelVariable = () => {
    setShowVariableModal(false);
    setVariableModalName('');
    setVariableModalDescription('');
    setVariableModalRequired(false);
    setEditingVariableIndex(null);
  };

  const removeVariable = (index: number) => {
    if (selectedToolIndex === null) return;

    const tool = vmcpConfig.custom_tools[selectedToolIndex];
    if (!tool.variables) return;

    const variable = tool.variables[index];

    // Remove var() syntax from tool text
    tool.text = tool.text.replace(new RegExp(`var\\(${variable.name}\\)`, 'g'), '');

    // Remove the variable
    tool.variables.splice(index, 1);

    // Update the VMCP config
    setVmcpConfig(prev => ({
      ...prev,
      custom_tools: prev.custom_tools.map((t, i) =>
        i === selectedToolIndex ? tool : t
      )
    }));
  };

  const handleTestTool = async () => {
    if (selectedToolIndex === null) return;

    setTestToolLoading(true);
    setTestToolError(null);
    setTestToolResult(null);

    try {
      const tool = vmcpConfig.custom_tools[selectedToolIndex];
      const toolName = tool.name;

      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available. Please log in again.');
      }

      // First, get the list of available tools from the vMCP
      const toolsResult = await apiClient.listVMCPTools(vmcpConfig.id, accessToken);

      if (!toolsResult.success) {
        throw new Error(toolsResult.error || 'Failed to fetch tools');
      }

      // Extract tools array from response structure
      // Backend returns: { success, message, data: { vmcp_id, tools: [...], total_tools: N } }
      // API client returns: { success: true, data: { vmcp_id, tools: [...], total_tools: N } }
      console.log('Tools result data:', toolsResult.data);
      const toolsList = Array.isArray(toolsResult.data?.tools) 
        ? toolsResult.data.tools 
        : Array.isArray(toolsResult.data) 
          ? toolsResult.data 
          : [];
      console.log('Extracted tools list:', toolsList);
      console.log('Looking for tool:', toolName);
      setAvailableTools(toolsList);

      // Check if the tool exists in the available tools
      const foundTool = Array.isArray(toolsList) ? toolsList.find((t: any) =>
        t.name === toolName
      ) : null;

      if (!foundTool) {
        const availableToolNames = toolsList.map((t: any) => t.name).join(', ');
        setTestToolError(
          `Tool "${toolName}" not found in available tools. ` +
          `Available tools: ${availableToolNames || 'none'}`
        );
        setTestToolLoading(false);
        return;
      }

      // Check if the tool has parameters
      const hasParameters = foundTool.inputSchema && foundTool.inputSchema.properties && Object.keys(foundTool.inputSchema.properties).length > 0;

      if (hasParameters) {
        // Show modal for parameter input
        setTestToolParameters({});
        setShowTestToolModal(true);
        setTestToolLoading(false);
      } else {
        // Execute tool directly without parameters
        await executeTool(toolName, {});
      }

    } catch (error) {
      console.error('Error testing tool:', error);
      setTestToolError(error instanceof Error ? error.message : 'An error occurred while testing the tool');
      setTestToolLoading(false);
    }
  };

  const executeTool = async (toolName: string, parameters: Record<string, any>) => {
    setTestToolLoading(true);
    setTestToolError(null);
    setTestToolResult(null);

    try {
      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available. Please log in again.');
      }

      // Create the tool request
      const toolRequest: VMCPToolCallRequest = {
        tool_name: `${toolName}`,
        arguments: parameters
      };

      // Execute the tool using apiClient
      console.log('Executing tool:', { toolName, parameters, vmcpId: vmcpConfig.id });
      const result = await apiClient.callVMCPTool(vmcpConfig.id, toolRequest, accessToken);
      console.log('Tool execution result:', result);

      if (!result.success) {
        throw new Error(result.error || 'Failed to execute tool');
      }

      // Extract the result text from the response
      // Backend returns: { success, message, data: { vmcp_id, tool, result: { content: [...], ... } } }
      // SDK wraps it: { success: true, data: { success, message, data: {...} } }
      // So we need: result.data.data.result.content
      let resultText = '';
      
      // Handle nested data structure from SDK
      const backendResponse = result.data?.data || result.data || {};
      
      console.log('Response data structure:', {
        'result.data': result.data,
        'result.data.data': result.data?.data,
        'backendResponse': backendResponse
      });
      
      // Extract content from result.result.content (the actual tool result)
      const toolResult = backendResponse.result || backendResponse;
      const content = toolResult.content;
      
      if (content) {
        if (Array.isArray(content)) {
          // Content is an array of content items (e.g., [{ type: "text", text: "Hello There" }, ...])
          resultText = content.map((item: any) => {
            if (typeof item === 'string') {
              return item;
            } else if (item.text) {
              return item.text;
            } else if (item.content) {
              return typeof item.content === 'string' ? item.content : JSON.stringify(item.content, null, 2);
            } else {
              return JSON.stringify(item, null, 2);
            }
          }).join('\n');
        } else if (typeof content === 'string') {
          resultText = content;
        } else if (content.text) {
          resultText = content.text;
        } else {
          resultText = JSON.stringify(content, null, 2);
        }
      }
      // Fallback: check if content is directly in backendResponse (for backward compatibility)
      else if (backendResponse.content) {
        const directContent = backendResponse.content;
        if (Array.isArray(directContent)) {
          resultText = directContent.map((item: any) => {
            if (typeof item === 'string') return item;
            if (item.text) return item.text;
            return JSON.stringify(item, null, 2);
          }).join('\n');
        } else if (typeof directContent === 'string') {
          resultText = directContent;
        } else {
          resultText = JSON.stringify(directContent, null, 2);
        }
      }
      // No content found - show error with full data for debugging
      else {
        const { vmcp_id, tool, tools, total_tools, ...restData } = backendResponse;
        if (Object.keys(restData).length > 0) {
          resultText = `Warning: No content field found in response. Response data:\n${JSON.stringify(restData, null, 2)}`;
        } else {
          resultText = `Error: Unexpected response structure. Full response:\n${JSON.stringify(backendResponse, null, 2)}`;
        }
        setTestToolError(resultText);
        setTestToolLoading(false);
        return;
      }

      setTestToolResult(resultText);
      setShowTestToolModal(false);

    } catch (error) {
      console.error('Error executing tool:', error);
      setTestToolError(error instanceof Error ? error.message : 'An error occurred while executing the tool');
    } finally {
      setTestToolLoading(false);
    }
  };

  const handleTestToolSubmit = () => {
    if (selectedToolIndex === null) return;

    const tool = vmcpConfig.custom_tools[selectedToolIndex];
    executeTool(tool.name, testToolParameters);
  };

  // MCP Server test functions
  const openMcpTestToolModal = (tool: any, serverId: string) => {
    console.log('Opening MCP test tool modal for:', tool.name, 'server:', serverId);
    const initialFormData: Record<string, any> = {};

    // Initialize form data based on input schema
    if (tool.inputSchema?.properties) {
      Object.keys(tool.inputSchema.properties).forEach(key => {
        const property = tool.inputSchema.properties[key];
        initialFormData[key] = getDefaultValue(property);
      });
    }

    console.log('Setting tool modal state:', {
      isOpen: true,
      tool,
      serverId,
      formData: initialFormData,
      testing: false,
    });

    setMcpTestToolModal({
      isOpen: true,
      tool,
      serverId,
      formData: initialFormData,
      testing: false,
      result: null,
      error: null,
    });
  };

  const closeMcpTestToolModal = () => {
    setMcpTestToolModal({
      isOpen: false,
      tool: null,
      serverId: null,
      formData: {},
      testing: false,
      result: null,
      error: null,
    });
  };

  const handleMcpToolFormChange = (key: string, value: any) => {
    setMcpTestToolModal(prev => ({
      ...prev,
      formData: {
        ...prev.formData,
        [key]: value,
      },
    }));
  };

  const executeMcpTool = async () => {
    if (!mcpTestToolModal.tool || !mcpTestToolModal.serverId) return;

    try {
      setMcpTestToolModal(prev => ({ ...prev, testing: true }));

      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available. Please log in again.');
      }

      // Create the tool request
      const toolRequest = {
        server_id: mcpTestToolModal.serverId,
        tool_name: mcpTestToolModal.tool.name,
        arguments: mcpTestToolModal.formData
      };

      // Execute the tool using apiClient
      const result = await apiClient.callMCPTool(mcpTestToolModal.serverId, toolRequest, accessToken);

      if (!result.success) {
        throw new Error(result.error || 'Failed to execute tool');
      }

      // Extract the result text from the response
      let resultText = '';
      if (result.data?.content && Array.isArray(result.data.content)) {
        resultText = result.data.content.map((item: any) =>
          item.text || JSON.stringify(item)
        ).join('\n');
      } else if (result.data?.content) {
        resultText = result.data.content;
      } else {
        resultText = JSON.stringify(result.data, null, 2);
      }

      // Store the result in the modal state instead of closing
      setMcpTestToolModal(prev => ({
        ...prev,
        result: resultText,
        error: null,
        testing: false,
      }));

    } catch (error) {
      console.error('Error executing MCP tool:', error);
      setMcpTestToolModal(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'An error occurred while executing the tool',
        testing: false,
      }));
    }
  };

  // Utility function for default values
  const getDefaultValue = (property: any): any => {
    if (property.default !== undefined) {
      return property.default;
    }

    switch (property.type) {
      case 'string':
        return '';
      case 'number':
      case 'integer':
        return 0;
      case 'boolean':
        return false;
      case 'array':
        return [];
      case 'object':
        return {};
      default:
        return '';
    }
  };

  // Tool override functions (per-tool)
  const openToolOverrideModal = (tool: any, serverId: string) => {
    setOverrideToolName(tool.name);
    setOverrideServerId(serverId);
    setOverrideTool(tool);

    // Load existing override values if they exist
    const existingOverride = (vmcpConfig.vmcp_config as any).selected_tool_overrides?.[serverId]?.[tool.name];
    setOverrideNameValue(existingOverride?.name || '');
    setOverrideDescriptionValue(existingOverride?.description || '');

    setShowToolOverrideModal(true);
  };

  const closeToolOverrideModal = () => {
    setShowToolOverrideModal(false);
    setOverrideToolName(null);
    setOverrideServerId(null);
    setOverrideTool(null);
    setOverrideNameValue('');
    setOverrideDescriptionValue('');
  };

  const saveToolOverride = async () => {
    if (!overrideToolName || !overrideServerId || !overrideTool) return;

    setSavingOverride(true);
    try {
      // Use the stored tool object instead of re-querying
      const tool = overrideTool;

      if (!tool) {
        error('Tool not found');
        return;
      }

      // Get existing overrides
      const existingOverrides = (vmcpConfig.vmcp_config as any).selected_tool_overrides?.[overrideServerId] || {};

      // Create or update the override for this tool
      const newOverride = {
        name: overrideNameValue.trim(),
        description: overrideDescriptionValue.trim(),
        originalName: tool.name,
        originalDescription: tool.description || ''
      };

      // Only save if there are actual changes
      const updatedOverrides = { ...existingOverrides };
      if (newOverride.name || newOverride.description) {
        updatedOverrides[overrideToolName] = newOverride;
      } else {
        // Remove override if both fields are empty
        delete updatedOverrides[overrideToolName];
      }

      // Update local state
      setVmcpConfig(prev => ({
        ...prev,
        vmcp_config: {
          ...prev.vmcp_config,
          selected_tool_overrides: {
            ...(prev.vmcp_config as any).selected_tool_overrides,
            [overrideServerId]: updatedOverrides
          }
        }
      }));

      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        error('No access token available. Please log in again.');
        return;
      }

      // Prepare the save data
      const saveData = {
        name: vmcpConfig.name,
        description: vmcpConfig.description,
        system_prompt: vmcpConfig.system_prompt,
        vmcp_config: {
          ...vmcpConfig.vmcp_config,
          selected_tool_overrides: {
            ...(vmcpConfig.vmcp_config as any).selected_tool_overrides,
            [overrideServerId]: updatedOverrides
          }
        },
        custom_prompts: vmcpConfig.custom_prompts,
        custom_tools: vmcpConfig.custom_tools,
        custom_context: vmcpConfig.custom_context,
        custom_resources: vmcpConfig.custom_resources,
        custom_resource_uris: vmcpConfig.custom_resource_uris,
        environment_variables: vmcpConfig.environment_variables,
        uploaded_files: vmcpConfig.uploaded_files,
        metadata: vmcpConfig.metadata
      };

      // Make API call to update VMCP
      // Convert Variable[] to PromptVariable[] format if needed
      const updateRequest: any = {
        ...saveData,
        system_prompt: saveData.system_prompt ? {
          ...saveData.system_prompt,
          variables: saveData.system_prompt.variables?.map((v: any) => ({
            name: v.name,
            description: v.description || '',
            required: v.required || false,
            ...(v.default !== undefined && { default: v.default }),
          })) || []
        } : undefined
      };
      const result = await apiClient.updateVMCP(vmcpConfig.id, updateRequest, accessToken);

      if (result.success) {
        // Refresh VMCP data to get the latest changes
        if (forceRefreshVMCPData) {
          await forceRefreshVMCPData();
        }
        success('Tool override saved successfully');
        closeToolOverrideModal();
      } else {
        console.error('Save failed:', result.error);
        error('Failed to save tool override');
      }
    } catch (err) {
      console.error('Error saving tool override:', err);
      error('Error saving tool override');
    } finally {
      setSavingOverride(false);
    }
  };

  const getToolDisplayName = (tool: any, serverId: string) => {
    const override = (vmcpConfig.vmcp_config as any).selected_tool_overrides?.[serverId]?.[tool.name];
    return override?.name || tool.name;
  };

  const getToolDisplayDescription = (tool: any, serverId: string) => {
    const override = (vmcpConfig.vmcp_config as any).selected_tool_overrides?.[serverId]?.[tool.name];
    return override?.description || tool.description || '';
  };

  const handleSavePromptTool = () => {
    if (selectedToolIndex !== null && vmcpConfig.custom_tools[selectedToolIndex]) {
      const currentTool = vmcpConfig.custom_tools[selectedToolIndex];
      setVmcpConfig(prev => ({
        ...prev,
        custom_tools: prev.custom_tools.map((t, i) =>
          i === selectedToolIndex ? { ...t, text: currentTool.text } : t
        )
      }));
      // setHasUnsavedChanges(false);
    }
  };

  const handleSavePythonTool = () => {
    if (selectedToolIndex !== null && vmcpConfig.custom_tools[selectedToolIndex]) {
      const currentTool = vmcpConfig.custom_tools[selectedToolIndex];
      setVmcpConfig(prev => ({
        ...prev,
        custom_tools: prev.custom_tools.map((t, i) =>
          i === selectedToolIndex ? { ...t, code: currentTool.code } : t
        )
      }));
      // setHasUnsavedChanges(false);
    }
  };

  const handleImportHttpTools = (endpoints: any[]) => {
    // Convert imported endpoints to HTTP tools with proper auth and parameters
    const newTools = endpoints.map(endpoint => {
      const name = (endpoint.name || '').toLowerCase().replace(/[^a-z0-9_]/g, '_') || 'api_tool';

      // Convert headers array to object format
      const headersObj: Record<string, string> = {};
      if (endpoint.headers && Array.isArray(endpoint.headers)) {
        endpoint.headers.forEach((header: any) => {
          if (header.key && header.value) {
            headersObj[header.key] = header.value;
          }
        });
      }

      // Convert query params array to object format and create variables
      const queryParamsObj: Record<string, string> = {};
      const variables: Array<{ name: string; description: string; required: boolean; type: string }> = [];

      if (endpoint.queryParams && Array.isArray(endpoint.queryParams)) {
        endpoint.queryParams.forEach((param: any) => {
          if (param.key && param.value) {
            // Check if value contains variables
            if (param.value.includes('{{') && param.value.includes('}}')) {
              // Extract variable name and create parameter
              const varMatch = param.value.match(/\{\{([^}]+)\}\}/);
              if (varMatch) {
                const varName = varMatch[1];
                variables.push({
                  name: varName,
                  description: `Query parameter: ${param.key}`,
                  required: true,
                  type: 'string'
                });
                queryParamsObj[param.key] = `@param.${varName}`;
              } else {
                queryParamsObj[param.key] = param.value;
              }
            } else {
              queryParamsObj[param.key] = param.value;
            }
          }
        });
      }

      // Add auth headers if present
      if (endpoint.auth) {
        if (endpoint.auth.type === 'bearer' && endpoint.auth.token) {
          if (endpoint.auth.token.includes('{{') && endpoint.auth.token.includes('}}')) {
            const varMatch = endpoint.auth.token.match(/\{\{([^}]+)\}\}/);
            if (varMatch) {
              const varName = varMatch[1];
              variables.push({
                name: varName,
                description: `Bearer token for authentication`,
                required: true,
                type: 'string'
              });
              headersObj['Authorization'] = `Bearer @param.${varName}`;
            } else {
              headersObj['Authorization'] = `Bearer ${endpoint.auth.token}`;
            }
          } else {
            headersObj['Authorization'] = `Bearer ${endpoint.auth.token}`;
          }
        } else if (endpoint.auth.type === 'apikey' && endpoint.auth.apiKey) {
          if (endpoint.auth.apiKey.includes('{{') && endpoint.auth.apiKey.includes('}}')) {
            const varMatch = endpoint.auth.apiKey.match(/\{\{([^}]+)\}\}/);
            if (varMatch) {
              const varName = varMatch[1];
              variables.push({
                name: varName,
                description: `API key for authentication`,
                required: true,
                type: 'string'
              });
              headersObj['X-API-Key'] = `@param.${varName}`;
            } else {
              headersObj['X-API-Key'] = endpoint.auth.apiKey;
            }
          } else {
            headersObj['X-API-Key'] = endpoint.auth.apiKey;
          }
        } else if (endpoint.auth.type === 'basic' && endpoint.auth.username && endpoint.auth.password) {
          // For basic auth, we'll create variables for username and password
          if (endpoint.auth.username.includes('{{') && endpoint.auth.username.includes('}}')) {
            const varMatch = endpoint.auth.username.match(/\{\{([^}]+)\}\}/);
            if (varMatch) {
              const varName = varMatch[1];
              variables.push({
                name: varName,
                description: `Username for basic authentication`,
                required: true,
                type: 'string'
              });
            }
          }
          if (endpoint.auth.password.includes('{{') && endpoint.auth.password.includes('}}')) {
            const varMatch = endpoint.auth.password.match(/\{\{([^}]+)\}\}/);
            if (varMatch) {
              const varName = varMatch[1];
              variables.push({
                name: varName,
                description: `Password for basic authentication`,
                required: true,
                type: 'string'
              });
            }
          }
        }
      }

      // Add any additional parameters from the endpoint
      if (endpoint.parameters && Array.isArray(endpoint.parameters)) {
        endpoint.parameters.forEach((param: any) => {
          // Check if parameter already exists
          const existingParam = variables.find(v => v.name === param.name);
          if (!existingParam) {
            variables.push(param);
          }
        });
      }

      // Process URL variables
      if (endpoint.url && endpoint.url.includes('{{') && endpoint.url.includes('}}')) {
        const urlVars = endpoint.url.match(/\{\{([^}]+)\}\}/g);
        if (urlVars) {
          urlVars.forEach((varMatch: string) => {
            const varName = varMatch.replace(/\{\{|\}\}/g, '');
            const existingParam = variables.find(v => v.name === varName);
            if (!existingParam) {
              variables.push({
                name: varName,
                description: `URL variable: ${varName}`,
                required: true,
                type: 'string'
              });
            }
          });
        }
      }

      // Process URL query parameters
      if (endpoint.url) {
        const queryParams = extractQueryParams(endpoint.url);
        queryParams.forEach(queryParam => {
          const existingParam = variables.find(v => v.name === queryParam.name);
          if (!existingParam) {
            variables.push({
              name: queryParam.name,
              description: queryParam.description,
              required: queryParam.required,
              type: queryParam.type
            });
          }
        });
      }

      // Process request body variables
      if (endpoint.body) {
        try {
          const bodyObj = typeof endpoint.body === 'string' ? JSON.parse(endpoint.body) : endpoint.body;
          const bodyVars = extractVariablesFromJson(bodyObj);
          bodyVars.forEach(newVar => {
            const existingParam = variables.find(v => v.name === newVar.name);
            if (!existingParam) {
              variables.push(newVar);
            }
          });
        } catch (e) {
          // If body is not valid JSON, treat it as a string and look for variables
          if (typeof endpoint.body === 'string' && endpoint.body.includes('{{') && endpoint.body.includes('}}')) {
            const bodyVars = endpoint.body.match(/\{\{([^}]+)\}\}/g);
            if (bodyVars) {
              bodyVars.forEach((varMatch: string) => {
                const varName = varMatch.replace(/\{\{|\}\}/g, '');
                const existingParam = variables.find(v => v.name === varName);
                if (!existingParam) {
                  variables.push({
                    name: varName,
                    description: `Body variable: ${varName}`,
                    required: true,
                    type: 'string'
                  });
                }
              });
            }
          }
        }
      }

      // Create parsed body with @param placeholders
      let bodyParsed = null;
      if (endpoint.body) {
        try {
          const bodyObj = typeof endpoint.body === 'string' ? JSON.parse(endpoint.body) : endpoint.body;
          bodyParsed = createParsedBody(bodyObj);
        } catch (e) {
          // If not valid JSON, keep as string
          bodyParsed = endpoint.body;
        }
      }

      return {
        name,
        description: endpoint.description || `HTTP ${endpoint.method} request to ${endpoint.url}`,
        text: '',
        variables: variables,
        environment_variables: [],
        tool_calls: [],
        tool_type: 'http' as const,
        api_config: {
          method: endpoint.method,
          url: endpoint.url,
          headers: headersObj,
          body: endpoint.body || '',
          body_parsed: bodyParsed,
          query_params: queryParamsObj
        },
        imported_from: endpoint.collectionMetadata ? 'postman' as const : 'openapi' as const
      };
    });

    // Add the new tools to the vMCP config
    setVmcpConfig(prev => {
      // Add config variable if any API keys detected
      const newEnvVars = [...prev.environment_variables];
      endpoints.forEach((ep: any) => {
        if (ep.apiKey) {
          const exists = newEnvVars.some(v => v.name === ep.apiKey.varName);
          if (!exists) {
            newEnvVars.push({ name: ep.apiKey.varName, value: '', description: `API key for ${ep.name}`, required: true, source: 'custom_tool' });
          }
        }
      });

      return {
        ...prev,
        environment_variables: newEnvVars,
        custom_tools: [...prev.custom_tools, ...newTools]
      };
    });

    setShowHttpImporter(false);
  };

  const handleCancelHttpImporter = () => {
    setShowHttpImporter(false);
  };

  if ((toolViewMode === 'edit') && selectedToolIndex !== null && vmcpConfig.custom_tools[selectedToolIndex]) {
    const tool = vmcpConfig.custom_tools[selectedToolIndex];
    if (!tool.variables) tool.variables = [];

    const toolType = tool.tool_type || 'prompt';

    console.log(`Rendering tool editor for tool: {tool.name}, type: ${toolType}`);

    return (
      <div>
        <div className="flex items-center justify-between gap-2 mb-4">
          <div className="flex-1 items-center gap-2">
            <h2 className="text-xl font-semibold text-foreground flex items-center gap-2">
              <ToolIcon className="h-5 w-5 text-primary" />
              {isRemoteVMCP ? 'View' : 'Edit' + " " + toolType.charAt(0).toUpperCase() + toolType.slice(1)} Tool
            </h2>

          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={handleTestTool}
            disabled={testToolLoading}
          >
            {testToolLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            Test Tool
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              // Dont save empty tool 
              if (vmcpConfig.custom_tools[selectedToolIndex].name.trim() === '') {
                removeCustomTool(selectedToolIndex);
              }
              setToolViewMode('list');
              setShowVariableModal(false);
              setEditingIndex(null);
              setEditingVariableIndex(null);
            }}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-col lg:flex-row gap-4">
          {/* Tool Content */}
          <div className='flex-1 gap-16 min-w-2xl'>
            <div className="space-y-4">
              <div className='grid grid-cols-1 md:grid-cols-3 gap-y-2 gap-x-4 items-stretch'>
                <label className="block col-span-1 text-sm font-medium text-muted-foreground">
                  Tool Name
                </label>
                <label className="block col-span-2 text-sm font-medium text-muted-foreground">
                  Keywords <span className="text-xs text-muted-foreground">(will be appended to the tool description to help with model steering)</span>
                </label>
                <Input
                  type="text"
                  disabled={isRemoteVMCP}
                  defaultValue={vmcpConfig.custom_tools[selectedToolIndex].name}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (/[^A-Za-z0-9_]/.test(value)) {
                      e.target.classList.add('border-red-500', 'focus:border-red-500');
                      const errorMsg = e.target.parentNode?.querySelector('.error-message');
                      if (errorMsg) {
                        errorMsg.textContent = 'Tool name can only contain letters, numbers, and underscores';
                        errorMsg.classList.remove('hidden');
                      }
                      return;
                    } else {
                      e.target.classList.remove('border-red-500', 'focus:border-red-500');
                      const errorMsg = e.target.parentNode?.querySelector('.error-message');
                      if (errorMsg) {
                        errorMsg.classList.add('hidden');
                      }
                      setVmcpConfig(prev => ({
                        ...prev,
                        custom_tools: prev.custom_tools.map((t, i) =>
                          i === selectedToolIndex ? { ...t, name: value } : t
                        )
                      }));
                    }
                  }}
                  placeholder="Enter tool name (letters, numbers, and underscores only)"
                />
                <div className="error-message hidden text-accent text-sm mt-1">
                  Tool name can only contain letters, numbers, and underscores
                </div>
                {/* Keywords */}
                <Input
                  className='col-span-2'
                  type="text"
                  disabled={isRemoteVMCP}
                  defaultValue={vmcpConfig.custom_tools[selectedToolIndex].keywords?.join(', ') || ''}
                  onChange={(e) => {
                    const keywords = e.target.value.split(',').map(k => k.trim()).filter(k => k.length > 0);
                    setVmcpConfig(prev => ({
                      ...prev,
                      custom_tools: prev.custom_tools.map((t, i) =>
                        i === selectedToolIndex ? { ...t, keywords } : t
                      )
                    }));
                  }}
                  placeholder="Enter keywords separated by commas (e.g. analysis, data, report)"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">
                  Description
                </label>
                <Input
                  type="text"
                  disabled={isRemoteVMCP}
                  defaultValue={vmcpConfig.custom_tools[selectedToolIndex].description}
                  onChange={(e) => {
                    setVmcpConfig(prev => ({
                      ...prev,
                      custom_tools: prev.custom_tools.map((t, i) =>
                        i === selectedToolIndex ? { ...t, description: e.target.value } : t
                      )
                    }));
                  }}
                  placeholder="What does this tool do? (This tells the model when to use it)"
                />
              </div>


              {/* Tool Content Editor - Different based on tool type */}
              {toolType === 'prompt' && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-muted-foreground">
                      Tool Text <span className="text-xs text-muted-foreground">(use @ to mention params, config, tools and resources)</span>
                    </label>

                  </div>
                  <VMCPMonacoEditor
                    value={vmcpConfig.custom_tools[selectedToolIndex].text}
                    readOnly={isRemoteVMCP}
                    onChange={(text) => {
                      setVmcpConfig(prev => ({
                        ...prev,
                        custom_tools: prev.custom_tools.map((t, i) =>
                          i === selectedToolIndex ? { ...t, text } : t
                        )
                      }));
                    }}
                    height={300}
                    vmcpConfig={vmcpConfig}
                    editKey="custom_tool"
                    editIndex={selectedToolIndex}
                    language="python"
                    setVmcpConfig={setVmcpConfig}
                  />
                </div>
              )}

              {toolType === 'python' && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-muted-foreground">
                      Python Function Code
                    </label>

                  </div>
                  <VMCPMonacoEditor
                    value={vmcpConfig.custom_tools[selectedToolIndex].code || ''}
                    onChange={(code) => {
                      setVmcpConfig(prev => ({
                        ...prev,
                        custom_tools: prev.custom_tools.map((t, i) =>
                          i === selectedToolIndex ? { ...t, code } : t
                        )
                      }));
                    }}
                    height={400}
                    vmcpConfig={vmcpConfig}
                    editKey="custom_tool"
                    editIndex={selectedToolIndex}
                    language="python"
                  />
                  <div className="mt-2 text-xs text-muted-foreground">
                    Write a Python function that will be executed securely. Use @param.variable_name for parameters and @config.CONFIG_VAR for environment variables.
                  </div>
                </div>
              )}

              {toolType === 'http' && (
                <div className="flex flex-col border border-muted-foreground/70 p-2 md:p-4 gap-2 rounded">
                  <div className="flex items-center justify-between mb-2 gap-2">
                    {/* HTTP Method */}
                    <div className='text-accent'>
                      <label className="block text-sm font-medium text-muted-foreground mb-2">
                        Method
                      </label>
                      <Select
                        value={vmcpConfig.custom_tools[selectedToolIndex].api_config?.method || 'GET'}
                        onValueChange={(value) => {
                          setVmcpConfig(prev => ({
                            ...prev,
                            custom_tools: prev.custom_tools.map((t, i) =>
                              i === selectedToolIndex
                                ? {
                                    ...t,
                                    api_config: {
                                      ...(t.api_config || {
                                        method: 'GET',
                                        url: '',
                                        headers: {},
                                        body: null,
                                        query_params: {}
                                      }),
                                      method: value
                                    }
                                  }
                                : t
                            )
                          }));
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="GET">GET</SelectItem>
                          <SelectItem value="POST">POST</SelectItem>
                          <SelectItem value="PUT">PUT</SelectItem>
                          <SelectItem value="PATCH">PATCH</SelectItem>
                          <SelectItem value="DELETE">DELETE</SelectItem>

                        </SelectContent>

                      </Select>
                    </div>
                    {/* URL */}
                    <div className='flex-1'>
                      <label className="block text-sm font-medium text-muted-foreground mb-2">
                        URL
                      </label>
                      <Input
                        type="text"
                        value={vmcpConfig.custom_tools[selectedToolIndex].api_config?.url || ''}
                        onChange={(e) => {
                          setVmcpConfig(prev => ({
                            ...prev,
                            custom_tools: prev.custom_tools.map((t, i) =>
                              i === selectedToolIndex
                                ? {
                                    ...t,
                                    api_config: {
                                      ...(t.api_config || {
                                        method: 'GET',
                                        url: '',
                                        headers: {},
                                        body: null,
                                        query_params: {}
                                      }),
                                      url: e.target.value
                                    }
                                  }
                                : t
                            )
                          }));
                        }}
                        placeholder="https://api.example.com/endpoint"
                      />
                    </div>
                  </div>
                  
                  <Separator className="my-2" />  

                  <div>
                    <div className="flex justify-between gap-2">
                      <label className="block text-sm font-medium text-muted-foreground">
                        Headers
                      </label>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setVmcpConfig(prev => {
                            const tool = prev.custom_tools[selectedToolIndex];
                            const apiConfig = tool.api_config || {
                              method: 'GET',
                              url: '',
                              headers: {},
                              body: null,
                              query_params: {}
                            };
                            const currentHeaders = apiConfig.headers || {};
                            const headerArray = Object.entries(currentHeaders).map(([key, value]) => ({ key, value }));
                            headerArray.push({ key: '', value: '' });
                            
                            return {
                              ...prev,
                              custom_tools: prev.custom_tools.map((t, i) =>
                                i === selectedToolIndex
                                  ? {
                                      ...t,
                                      api_config: {
                                        ...apiConfig,
                                        headers_array: headerArray
                                      }
                                    }
                                  : t
                              )
                            };
                          });
                        }}
                      >
                        <Plus className="h-3 w-3 mr-1" />
                      </Button>
                    </div>
                    <div className="space-y-2">
                      {((vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.headers_array ||
                        Object.entries(vmcpConfig.custom_tools[selectedToolIndex].api_config?.headers || {}).map(([key, value]) => ({ key, value }))
                      ).map((header: any, index: number) => (
                        <div key={index} className="flex gap-2">
                          <Input
                            type="text"
                            placeholder="Header name"
                            defaultValue={header.key}
                            onChange={(e) => {
                              setVmcpConfig(prev => {
                                const tool = prev.custom_tools[selectedToolIndex];
                                const apiConfig = tool.api_config || {
                                  method: 'GET',
                                  url: '',
                                  headers: {},
                                  body: null,
                                  query_params: {}
                                };
                                const headersArray = (apiConfig as any).headers_array || 
                                  Object.entries(apiConfig.headers || {}).map(([key, value]) => ({ key, value }));
                                const newHeadersArray = headersArray.map((h: any, i: number) =>
                                  i === index ? { ...h, key: e.target.value } : h
                                );
                                const headersObj: Record<string, string> = {};
                                newHeadersArray.forEach((h: any) => {
                                  if (h.key && h.value) {
                                    headersObj[h.key] = h.value;
                                  }
                                });
                                
                                return {
                                  ...prev,
                                  custom_tools: prev.custom_tools.map((t, i) =>
                                    i === selectedToolIndex
                                      ? {
                                          ...t,
                                          api_config: {
                                            ...apiConfig,
                                            headers: headersObj,
                                            headers_array: newHeadersArray
                                          }
                                        }
                                      : t
                                  )
                                };
                              });
                            }}
                            className="font-mono"
                          />
                          <Input
                            type="text"
                            placeholder="Header value"
                            defaultValue={header.value}
                            onChange={(e) => {
                              setVmcpConfig(prev => {
                                const tool = prev.custom_tools[selectedToolIndex];
                                const apiConfig = tool.api_config || {
                                  method: 'GET',
                                  url: '',
                                  headers: {},
                                  body: null,
                                  query_params: {}
                                };
                                const headersArray = (apiConfig as any).headers_array || 
                                  Object.entries(apiConfig.headers || {}).map(([key, value]) => ({ key, value }));
                                const newHeadersArray = headersArray.map((h: any, i: number) =>
                                  i === index ? { ...h, value: e.target.value } : h
                                );
                                const headersObj: Record<string, string> = {};
                                newHeadersArray.forEach((h: any) => {
                                  if (h.key && h.value) {
                                    headersObj[h.key] = h.value;
                                  }
                                });
                                
                                return {
                                  ...prev,
                                  custom_tools: prev.custom_tools.map((t, i) =>
                                    i === selectedToolIndex
                                      ? {
                                          ...t,
                                          api_config: {
                                            ...apiConfig,
                                            headers: headersObj,
                                            headers_array: newHeadersArray
                                          }
                                        }
                                      : t
                                  )
                                };
                              });
                            }}
                            className="font-mono"
                          />
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setVmcpConfig(prev => {
                                const tool = prev.custom_tools[selectedToolIndex];
                                const apiConfig = tool.api_config || {
                                  method: 'GET',
                                  url: '',
                                  headers: {},
                                  body: null,
                                  query_params: {}
                                };
                                const headersArray = (apiConfig as any).headers_array || 
                                  Object.entries(apiConfig.headers || {}).map(([key, value]) => ({ key, value }));
                                const newHeadersArray = headersArray.filter((_: any, i: number) => i !== index);
                                const headersObj: Record<string, string> = {};
                                newHeadersArray.forEach((h: any) => {
                                  if (h.key && h.value) {
                                    headersObj[h.key] = h.value;
                                  }
                                });
                                
                                return {
                                  ...prev,
                                  custom_tools: prev.custom_tools.map((t, i) =>
                                    i === selectedToolIndex
                                      ? {
                                          ...t,
                                          api_config: {
                                            ...apiConfig,
                                            headers: headersObj,
                                            headers_array: newHeadersArray
                                          }
                                        }
                                      : t
                                  )
                                };
                              });
                            }}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                  <Separator className="my-2" />
                  <div className='flex gap-2 items-center'>
                    <div className='w-[200px]'>
                      <Label className="block text-sm font-medium text-muted-foreground mb-2">
                        Authentication
                      </Label>
                      <Select
                        value={(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.type || 'none'}
                        onValueChange={(value) => {
                          console.log('Auth type changed to:', value);
                          if (!vmcpConfig.custom_tools[selectedToolIndex].api_config) {
                            vmcpConfig.custom_tools[selectedToolIndex].api_config = {
                              method: 'GET',
                              url: '',
                              headers: {},
                              body: null,
                              query_params: {}
                            };
                          }
                          // Initialize auth if it doesn't exist
                          if (!(vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth) {
                            (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth = {};
                          }
                          (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth.type = value as 'none' | 'bearer' | 'apikey' | 'basic';
                          setVmcpConfig({ ...vmcpConfig });
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">None</SelectItem>
                          <SelectItem value="bearer">Bearer Token</SelectItem>
                          <SelectItem value="apikey">API Key</SelectItem>
                          <SelectItem value="basic">Basic Auth</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className='flex-1 text-xs text-muted-foreground'>
                      {(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.type === 'bearer' && (
                        <div>
                          <Label className="block text-sm text-muted-foreground mb-2">Token</Label>
                          <Input
                            type="text"
                            defaultValue={(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.token || ''}
                            onChange={(e) => {
                              if (!vmcpConfig.custom_tools[selectedToolIndex].api_config) {
                                vmcpConfig.custom_tools[selectedToolIndex].api_config = {
                                  method: 'GET',
                                  url: '',
                                  headers: {},
                                  body: null,
                                  query_params: {}
                                };
                              }
                              if (!(vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth) {
                                (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth = { type: 'bearer' };
                              }
                              (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth.token = e.target.value;
                            }}
                            placeholder="Bearer token or {{TOKEN}}"
                            className="font-mono"
                          />
                        </div>
                      )}

                      {(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.type === 'apikey' && (
                        <div>
                          <label className="block text-sm text-muted-foreground mb-2">API Key</label>
                          <Input
                            type="text"
                            defaultValue={(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.apiKey || ''}
                            onChange={(e) => {
                              console.log('API Key changed to:', e.target.value);
                              if (!vmcpConfig.custom_tools[selectedToolIndex].api_config) {
                                vmcpConfig.custom_tools[selectedToolIndex].api_config = {
                                  method: 'GET',
                                  url: '',
                                  headers: {},
                                  body: null,
                                  query_params: {}
                                };
                              }
                              if (!(vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth) {
                                (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth = { type: 'apikey' };
                              }
                              (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth.apiKey = e.target.value;
                            }}
                            placeholder="API key or {{API_KEY}}"
                            className="font-mono"
                          />
                        </div>
                      )}

                      {(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.type === 'basic' && (
                        <div className="flex w-full place-items-stretch gap-2">
                          <div className='flex-1'>
                            <label className="block text-sm text-muted-foreground mb-2">Username</label>
                            <Input
                              type="text"
                              defaultValue={(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.username || ''}
                              onChange={(e) => {
                                if (!vmcpConfig.custom_tools[selectedToolIndex].api_config) {
                                  vmcpConfig.custom_tools[selectedToolIndex].api_config = {
                                    method: 'GET',
                                    url: '',
                                    headers: {},
                                    body: null,
                                    query_params: {}
                                  };
                                }
                                if (!(vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth) {
                                  (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth = { type: 'basic' };
                                }
                                (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth.username = e.target.value;
                              }}
                              placeholder="Username or {{USERNAME}}"
                              className="font-mono"
                            />
                          </div>
                          <div className='flex-1'>
                            <label className="block text-sm text-muted-foreground mb-2">Password</label>
                            <Input
                              type="password"
                              defaultValue={(vmcpConfig.custom_tools[selectedToolIndex].api_config as any)?.auth?.password || ''}
                              onChange={(e) => {
                                if (!vmcpConfig.custom_tools[selectedToolIndex].api_config) {
                                  vmcpConfig.custom_tools[selectedToolIndex].api_config = {
                                    method: 'GET',
                                    url: '',
                                    headers: {},
                                    body: null,
                                    query_params: {}
                                  };
                                }
                                if (!(vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth) {
                                  (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth = { type: 'basic' };
                                }
                                (vmcpConfig.custom_tools[selectedToolIndex].api_config as any).auth.password = e.target.value;
                              }}
                              placeholder="Password or {{PASSWORD}}"
                              className="font-mono"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  

                  {vmcpConfig.custom_tools[selectedToolIndex].api_config?.method !== 'GET' && (
                    <div>
                      <Separator className="my-2" />
                      <label className="block text-sm font-medium text-muted-foreground py-2">
                        Request Body (JSON)
                      </label>
                      <VMCPMonacoEditor
                        value={vmcpConfig.custom_tools[selectedToolIndex].api_config?.body_parsed ?
                          JSON.stringify(vmcpConfig.custom_tools[selectedToolIndex].api_config.body_parsed, null, 2) :
                          vmcpConfig.custom_tools[selectedToolIndex].api_config?.body ?
                            (typeof vmcpConfig.custom_tools[selectedToolIndex].api_config.body === 'string'
                              ? vmcpConfig.custom_tools[selectedToolIndex].api_config.body
                              : JSON.stringify(vmcpConfig.custom_tools[selectedToolIndex].api_config.body, null, 2)
                            ) : '{}'}
                        onChange={(bodyJson) => {
                          try {
                            const body = JSON.parse(bodyJson);
                            setVmcpConfig(prev => {
                              const tool = prev.custom_tools[selectedToolIndex];
                              const apiConfig = tool.api_config || {
                                method: 'GET',
                                url: '',
                                headers: {},
                                body: null,
                                query_params: {}
                              };
                              
                              // Create parsed body with @param placeholders
                              const bodyParsed = createParsedBody(body);
                              
                              // Extract variables from JSON body and create parameters
                              const extractedVars = extractVariablesFromJson(body);
                              const currentVars = tool.variables || [];
                              const newVars = [...currentVars];
                              
                              extractedVars.forEach(newVar => {
                                const existingVar = newVars.find(v => v.name === newVar.name);
                                if (!existingVar) {
                                  newVars.push(newVar);
                                }
                              });
                              
                              return {
                                ...prev,
                                custom_tools: prev.custom_tools.map((t, i) =>
                                  i === selectedToolIndex
                                    ? {
                                        ...t,
                                        api_config: {
                                          ...apiConfig,
                                          body,
                                          body_parsed: bodyParsed
                                        },
                                        variables: newVars
                                      }
                                    : t
                                )
                              };
                            });
                          } catch (e) {
                            // Invalid JSON, don't update
                          }
                        }}
                        height={150}
                        vmcpConfig={vmcpConfig}
                        editKey="custom_tool"
                        editIndex={selectedToolIndex}
                        language="json"
                        showSyntaxGuide={false}
                      />
                    </div>
                  )}
              </div>
              )}
            </div>
          </div>

          {/* Variables */}
          <div className='flex gap-2 basis-sm flex-col'>
            {/* Parameters Display (hidden for Python tools) */}
            {toolType !== 'python' && (
              <div className="bg-card p-2 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium underline underline-offset-4 decoration-accent text-foreground">Parameters</h4>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleAddVariable}
                    disabled={isRemoteVMCP}
                    title={isRemoteVMCP ? 'Adding parameters disabled for remote vMCPs' : ''}
                    className="h-6 w-6 p-0"
                  >
                    <Plus className="h-3 w-3" />
                  </Button>
                </div>
                <div className="space-y-2">
                  {tool.variables && tool.variables.length > 0 ? (
                    tool.variables.map((variable, varIndex) => (
                      <div key={`tool-var-${selectedToolIndex}-${varIndex}-${variable.name}`} className="rounded-lg p-3 border border-border">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-medium text-foreground">{variable.name}</span>
                              {variable.type && (
                                <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                                  {getTypeDisplayName(variable.type)}
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {variable.description || 'No description'}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={isRemoteVMCP}
                              onClick={() => handleEditVariable(varIndex)}
                              className="h-5 w-5 p-0"
                            >
                              <Edit className="h-3 w-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={isRemoteVMCP}
                              onClick={() => removeVariable(varIndex)}
                              className="h-5 w-5 p-0 text-destructive"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                        <div className="flex items-center">
                          <span className={`text-xs px-2 py-1 rounded ${variable.required
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-green-100 text-green-800'
                            }`}>
                            {variable.required ? 'Required' : 'Optional'}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center text-sm py-4 text-muted-foreground italic">
                      Add local parameters by clicking the + button and use them in prompt using param.[parameter_name]
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Config Display */}
            {/* <div className="bg-card p-2 rounded-2xl">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium underline underline-offset-4 decoration-accent text-foreground">Config</h4>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleAddNew}
                  disabled={isRemoteVMCP}
                  title={isRemoteVMCP ? 'Adding config variables disabled for remote vMCPs' : ''}
                  className="h-6 w-6 p-0"
                >
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              <div className="space-y-2">
                {vmcpConfig.environment_variables.length === 0 ? (
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    <p className="mb-2">No config variables defined yet.</p>
                    <p className="text-xs">Use config.[CONFIG_VAR] syntax in your content and click the + button to add them.</p>
                  </div>
                ) : (
                  vmcpConfig.environment_variables.map((envVar, varIndex) => (
                    <div key={`available-env-${varIndex}`} className="bg-muted/20 rounded-lg p-2 border border-border/50">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-medium text-foreground font-mono">{envVar.name}</span>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleEdit(varIndex)}
                              className="h-5 w-5 p-0"
                            >
                              <Edit className="h-3 w-3" />
                            </Button>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {envVar.description || 'No description'}
                          </div>
                          <div className="text-xs text-foreground">
                            <span className="text-muted-foreground">Value: </span>
                            {envVar.value || <span className="text-muted-foreground italic">Not set</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-1 rounded ${
                            envVar.required 
                              ? 'bg-amber-100 text-amber-800' 
                              : 'bg-green-100 text-green-800'
                          }`}>
                            {envVar.required ? 'Required' : 'Optional'}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div> */}
          </div>
        </div>


        {/* Add/Edit Local Variable Modal */}
        {showVariableModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-lg">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                {editingVariableIndex !== null ? 'Edit Local Parameter' : 'Add Local Parameter'}
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Parameter Name
                  </label>
                  <Input
                    type="text"
                    value={variableModalName}
                    onChange={(e) => setVariableModalName(e.target.value)}
                    placeholder="PARAMETER_NAME"
                    className="font-mono"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Description
                  </label>
                  <Input
                    type="text"
                    value={variableModalDescription}
                    onChange={(e) => setVariableModalDescription(e.target.value)}
                    placeholder="What is this variable for?"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Data Type
                  </label>
                  <Select
                    value={variableModalDataType}
                    onValueChange={(value) => setVariableModalDataType(value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="str">String</SelectItem>
                      <SelectItem value="int">Integer</SelectItem>
                      <SelectItem value="float">Float</SelectItem>
                      <SelectItem value="bool">Boolean</SelectItem>
                      <SelectItem value="list">List</SelectItem>
                      <SelectItem value="dict">Dictionary</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="var-required"
                    checked={variableModalRequired}
                    onCheckedChange={(checked: boolean) => setVariableModalRequired(checked)}
                  />
                  <Label htmlFor="var-required" className="text-sm font-medium">
                    Required
                  </Label>
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <Button
                  variant="outline"
                  onClick={handleCancelVariable}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSaveVariable}
                  disabled={!variableModalName.trim() || selectedToolIndex === null}
                  className="flex-1"
                >
                  {editingVariableIndex !== null ? 'Update' : 'Add'}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Test Tool Modal */}
        {showTestToolModal && selectedToolIndex !== null && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-card border border-border rounded-lg p-6 max-w-2xl w-full mx-4 shadow-lg max-h-[80vh] overflow-y-auto">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Test Tool: {vmcpConfig.custom_tools[selectedToolIndex].name}
              </h3>

              {availableTools.length > 0 && Array.isArray(availableTools) && (() => {
                const toolName = vmcpConfig.custom_tools[selectedToolIndex].name;
                const foundTool = availableTools.find((t: any) =>
                  t.name === toolName || t.name === `${toolName}`
                );
                if (!foundTool) return null;

                return (
                  <div className="space-y-4">
                    <div className="text-sm text-muted-foreground mb-4">
                      {foundTool.description || 'No description available'}
                    </div>

                    {foundTool.inputSchema && foundTool.inputSchema.properties && Object.keys(foundTool.inputSchema.properties).length > 0 ? (
                      <div className="space-y-4">
                        <h4 className="font-medium text-foreground">Parameters:</h4>
                        {Object.entries(foundTool.inputSchema.properties).map(([key, prop]: [string, any]) => (
                          <div key={key} className="space-y-2">
                            <label className="block text-sm font-medium text-foreground">
                              {key}
                              {foundTool.inputSchema.required?.includes(key) && <span className="text-red-500 ml-1">*</span>}
                            </label>
                            <Input
                              type="text"
                              value={testToolParameters[key] || ''}
                              onChange={(e) => setTestToolParameters(prev => ({
                                ...prev,
                                [key]: e.target.value
                              }))}
                              placeholder={prop.description || `Enter ${key}`}
                            />
                            {prop.description && (
                              <p className="text-xs text-muted-foreground">{prop.description}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        This tool has no parameters.
                      </div>
                    )}
                  </div>
                );
              })()}

              <div className="flex gap-3 mt-6">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowTestToolModal(false);
                    setTestToolParameters({});
                  }}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleTestToolSubmit}
                  disabled={testToolLoading}
                  className="flex-1"
                >
                  {testToolLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Test Tool
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )
        }

        {/* Test Tool Result Display */}
        {(testToolResult || testToolError) && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-card border border-border rounded-lg p-6 max-w-4xl w-full mx-4 shadow-lg max-h-[80vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-foreground">
                  Test Tool Result
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setTestToolResult(null);
                    setTestToolError(null);
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {testToolError ? (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <h4 className="font-medium text-red-800 mb-2">Error:</h4>
                  <p className="text-red-700 text-sm">{testToolError}</p>
                </div>
              ) : (
                <div className="bg-muted/50 border border-border rounded-lg p-4">
                  <h4 className="font-medium text-foreground mb-2">Result:</h4>
                  <pre className="text-sm text-foreground whitespace-pre-wrap overflow-x-auto">
                    {testToolResult}
                  </pre>
                </div>
              )}

              <div className="flex justify-end mt-6">
                <Button
                  onClick={() => {
                    setTestToolResult(null);
                    setTestToolError(null);
                  }}
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}

      </div>
    );
  }


  return (
    <div>
      <Tabs defaultValue="custom-tools" className="w-full">
        <TabsList className="mb-4 bg-transparent p-0 h-auto justify-start w-full border-b-1">
          <TabsTrigger
            value="custom-tools"
            className="data-[state=active]:bg-background data-[state=active]:border-accent data-[state=active]:border-b-1 data-[state=active]:border-t-0 data-[state=active]:border-l-0 data-[state=active]:border-r-0 rounded-none"
          >
            <VmcpIcon className="h-4 w-4" />
            vMCP Tools
            <Badge variant="outline" className="ml-2 text-xs">
              {vmcpConfig.custom_tools.length}
            </Badge>
          </TabsTrigger>
          {vmcpConfig.vmcp_config.selected_servers.map((server) => {
            const fullServer = servers.find(s => s.id === server.server_id);
            const selectedTools = vmcpConfig.vmcp_config.selected_tools[server.server_id] || [];

            return (
              <TabsTrigger
                key={server.server_id}
                value={`server-${server.server_id}`}
                className="data-[state=active]:border-accent data-[state=active]:border-b-1 data-[state=active]:border-t-0 data-[state=active]:border-l-0 data-[state=active]:border-r-0 rounded-none"
              >
                <div className="flex items-center gap-2">
                  <McpIcon className="h-4 w-4" />
                  MCP: {server.name}
                </div>
                <Badge variant="outline" className="ml-2 text-xs">
                  {selectedTools.length}/{server?.tool_details?.length || 0}
                </Badge>
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="custom-tools">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-muted-foreground">Select a tool to edit or create a new one</p>
              <div className="flex gap-2">
                <Select
                  onValueChange={(value) => {
                    if (value === 'prompt') {
                      addCustomTool('prompt');
                      setSelectedToolIndex(vmcpConfig.custom_tools.length);
                      setToolViewMode('edit');
                    } else if (value === 'python') {
                      addCustomTool('python');
                      setSelectedToolIndex(vmcpConfig.custom_tools.length);
                      setToolViewMode('edit');
                    } else if (value === 'http') {
                      addCustomTool('http');
                      setSelectedToolIndex(vmcpConfig.custom_tools.length);
                      setToolViewMode('edit');
                    } else if (value === 'import') {
                      setShowHttpImporter(true);
                    }
                  }}
                  disabled={isRemoteVMCP}
                >
                  <SelectTrigger className="w-[200px] whitespace-nowrap h-8 p-2">
                    <div className="flex items-center gap-2">
                      <Plus className="size-4" />
                      <span className="text-sm">Add Tool</span>
                    </div>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="prompt">
                      <div className="flex items-center gap-2">
                        <PromptIcon className="h-4 w-4 text-primary" />
                        <span>Prompt Tool</span>
                      </div>
                    </SelectItem>
                    <SelectItem value="http">
                      <div className="flex items-center gap-2">
                        <Braces className="h-4 w-4 text-primary" />
                        <span>HTTP Tool</span>
                      </div>
                    </SelectItem>
                    <SelectItem value="python">
                      <div className="flex items-center gap-2">
                        <Code className="h-4 w-4 text-primary" />
                        <span>Python Tool</span>
                      </div>
                    </SelectItem>
                    <SelectItem value="import">
                      <div className="flex items-center gap-2">
                        <FolderInput className="h-4 w-4 text-primary" />
                        <span>Import Collection</span>
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {vmcpConfig.custom_tools.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No custom tools created yet. Click "Add Tool" to create your first custom tool.
              </div>
            ) : (
              <div className="grid gap-4">
                {vmcpConfig.custom_tools.map((tool, index) => (
                  <div
                    key={`tool-list-${index}-${tool.name || 'unnamed'}`}
                    className="bg-card rounded-lg p-4 border border-border hover:border-primary cursor-pointer transition-colors"
                    onClick={() => {
                      setSelectedToolIndex(index);
                      setToolViewMode('edit');
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-medium text-foreground">{tool.name || `Tool ${index + 1}`}</h3>
                          <Badge variant="outline" className="text-xs">
                            {tool.tool_type || 'prompt'}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{tool.description || 'No description'}</p>
                        {tool.keywords && tool.keywords.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {tool.keywords.map((keyword, kIndex) => (
                              <Badge key={kIndex} variant="secondary" className="text-xs px-2 py-0">
                                {keyword}
                              </Badge>
                            ))}
                          </div>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">
                          {tool.tool_type === 'python'
                            ? (tool.code ? `Python function: ${tool.code.substring(0, 100)}${tool.code.length > 100 ? '...' : ''}` : 'No Python code')
                            : tool.tool_type === 'http'
                              ? (tool.api_config?.url ? `HTTP ${tool.api_config.method}: ${tool.api_config.url}` : 'No HTTP configuration')
                              : (tool.text ? `${tool.text.substring(0, 100)}${tool.text.length > 100 ? '...' : ''}` : 'No content')
                          }
                        </p>
                      </div>
                      {!isRemoteVMCP && (<Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeCustomTool(index);
                        }}
                        className="hover:text-destructive/80"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {vmcpConfig.vmcp_config.selected_servers.map((server) => {
          // First try to find the server in the vMCP configuration (it has the full server data)
          let fullServer = server;
          // If the server doesn't have tool_details, try to find it in the servers context
          if (!fullServer.tool_details && servers) {
            fullServer = servers.find(s => s.server_id === server.server_id) || server;
          }
          const serverTools = fullServer?.tool_details || [];
          const selectedTools = vmcpConfig.vmcp_config.selected_tools[server.server_id] || [];

          return (
            <TabsContent key={server.server_id} value={`server-${server.server_id}`}>
              <div className="space-y-4">

                <div className="flex w-full items-center place-content-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const allToolNames = serverTools.map((t: any) => t.name);
                      setVmcpConfig(prev => ({
                        ...prev,
                        vmcp_config: {
                          ...prev.vmcp_config,
                          selected_tools: {
                            ...prev.vmcp_config.selected_tools,
                            [server.server_id]: allToolNames
                          }
                        }
                      }));
                    }}
                    disabled={isRemoteVMCP}
                    title={isRemoteVMCP ? 'Selection disabled for remote vMCPs' : ''}
                    className="h-7 px-3 text-xs border-muted"
                  >
                    Select All
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setVmcpConfig(prev => ({
                        ...prev,
                        vmcp_config: {
                          ...prev.vmcp_config,
                          selected_tools: {
                            ...prev.vmcp_config.selected_tools,
                            [server.server_id]: []
                          }
                        }
                      }));
                    }}
                    disabled={isRemoteVMCP}
                    title={isRemoteVMCP ? 'Selection disabled for remote vMCPs' : ''}
                    className="h-7 px-3 text-xs border-muted"
                  >
                    Deselect All
                  </Button>
                </div>

                {serverTools.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                      <ToolIcon className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <h4 className="text-base font-medium text-foreground mb-1">No Tools Available</h4>
                    <p className="text-sm text-muted-foreground">This MCP server doesn't expose any tools.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {serverTools.map((tool: any) => {
                      const hasSchema = tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0;
                      const hasOverride = (vmcpConfig.vmcp_config as any).selected_tool_overrides?.[server.server_id]?.[tool.name];
                      const isSelected = selectedTools.includes(tool.name);

                      return (
                        <div
                          key={tool.name}

                          className={cn(
                            "p-3 rounded-lg border transition-all duration-200 cursor-pointer",
                            hasOverride && isSelected
                              ? "bg-muted/60 border-accent/50 hover:border-accent/80"
                              : isSelected
                                ? "bg-muted/60 border-primary/50 hover:border-primary/80"
                                : "bg-muted/40 border-border/60 hover:bg-muted/60 hover:border-border/80"
                          )}
                          onClick={() => {
                            if (isRemoteVMCP) {
                              //Show error toast
                              error("Selection disabled for community vMCPs", {
                                description: "Extend the vMCP to make changes"
                              });
                              return; // Disable selection for remote vMCPs
                            }
                            const newSelected = new Set(selectedTools);
                            if (newSelected.has(tool.name)) {
                              newSelected.delete(tool.name);
                            } else {
                              newSelected.add(tool.name);
                            }

                            setVmcpConfig(prev => ({
                              ...prev,
                              vmcp_config: {
                                ...prev.vmcp_config,
                                selected_tools: {
                                  ...prev.vmcp_config.selected_tools,
                                  [server.server_id]: Array.from(newSelected)
                                }
                              }
                            }));
                          }}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <ToolIcon className="h-4 w-4 text-primary" />
                              <div className="flex flex-col">
                                <span className="font-medium text-sm">{getToolDisplayName(tool, server.server_id)}</span>
                                {(vmcpConfig.vmcp_config as any).selected_tool_overrides?.[server.server_id]?.[tool.name] && (
                                  <span className="text-xs text-muted-foreground">
                                    modified {tool.name}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openToolOverrideModal(tool, server.server_id);
                                }}
                                disabled={isRemoteVMCP}
                                title={isRemoteVMCP ? 'Override disabled for remote vMCPs' : 'Override tool name and description'}
                                className="h-6 px-2 text-xs opacity-60 hover:opacity-100 transition-opacity"
                              >
                                <Edit className="h-3 w-3 mr-1" />
                                Override
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  console.log('Test button clicked for tool:', tool.name);
                                  e.stopPropagation();
                                  openMcpTestToolModal(tool, server.server_id);
                                }}
                                className="h-6 px-2 text-xs opacity-60 hover:opacity-100 transition-opacity"
                              >
                                <Play className="h-3 w-3 mr-1" />
                                Test
                              </Button>
                              <div className={cn(
                                "w-4 h-4 rounded-full border-2 flex items-center justify-center",
                                selectedTools.includes(tool.name)
                                  ? "bg-primary border-primary"
                                  : "border-border"
                              )}>
                                {selectedTools.includes(tool.name) && (
                                  <div className="w-2 h-2 bg-primary-foreground rounded-full"></div>
                                )}
                              </div>
                            </div>
                          </div>
                          {(getToolDisplayDescription(tool, server.server_id) || tool.description) && (
                            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                              {getToolDisplayDescription(tool, server.server_id) || tool.description}
                            </p>
                          )}
                          {/* {hasSchema && (
                            <div className="mt-2">
                              <Badge variant="secondary" className="text-xs">
                                Has Parameters
                              </Badge>
                            </div>
                          )} */}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </TabsContent>
          );
        })}

        {/* Empty state when no servers are selected */}
        {vmcpConfig.vmcp_config.selected_servers.length === 0 && (
          <TabsContent value="no-servers">
            <div className="text-center py-8 text-muted-foreground">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                <McpIcon className="h-6 w-6 text-muted-foreground" />
              </div>
              <h4 className="text-base font-medium text-foreground mb-1">No MCP Servers Selected</h4>
              <p className="text-sm text-muted-foreground">Add MCP servers in the MCP Servers tab to see their tools here.</p>
            </div>
          </TabsContent>
        )}
      </Tabs>


      {/* MCP Test Tool Modal */}
      {mcpTestToolModal.isOpen && mcpTestToolModal.tool && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-2xl w-full mx-4 shadow-lg max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Test MCP Tool: {mcpTestToolModal.tool.name}
            </h3>

            <div className="space-y-4">
              <div className="text-sm text-muted-foreground mb-4">
                {mcpTestToolModal.tool.description || 'No description available'}
              </div>

              {mcpTestToolModal.tool.inputSchema?.properties && Object.keys(mcpTestToolModal.tool.inputSchema.properties).length > 0 ? (
                <div className="space-y-4">
                  <h4 className="font-medium text-foreground">Parameters:</h4>
                  {Object.entries(mcpTestToolModal.tool.inputSchema.properties).map(([key, property]: [string, any]) => (
                    <div key={key} className="space-y-2">
                      <label className="block text-sm font-medium text-foreground">
                        {key}
                        {mcpTestToolModal.tool.inputSchema.required?.includes(key) && <span className="text-red-500 ml-1">*</span>}
                      </label>
                      {property.type === 'string' && property.format === 'multiline' ? (
                        <textarea
                          value={mcpTestToolModal.formData[key] || ''}
                          onChange={(e) => handleMcpToolFormChange(key, e.target.value)}
                          placeholder={property.description || `Enter ${key}`}
                          rows={3}
                          className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground"
                        />
                      ) : property.type === 'boolean' ? (
                        <select
                          value={mcpTestToolModal.formData[key] || ''}
                          onChange={(e) => handleMcpToolFormChange(key, e.target.value === 'true')}
                          className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground"
                        >
                          <option value="">Select...</option>
                          <option value="true">True</option>
                          <option value="false">False</option>
                        </select>
                      ) : (
                        <Input
                          type={property.type === 'number' ? 'number' : 'text'}
                          value={mcpTestToolModal.formData[key] || ''}
                          onChange={(e) => handleMcpToolFormChange(key, property.type === 'number' ? Number(e.target.value) : e.target.value)}
                          placeholder={property.description || `Enter ${key}`}
                        />
                      )}
                      {property.description && (
                        <p className="text-xs text-muted-foreground">{property.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  This tool has no parameters.
                </div>
              )}
            </div>

            {/* Result Display */}
            {mcpTestToolModal.result && (
              <div className="mt-6">
                <h4 className="font-medium text-foreground mb-2">Result:</h4>
                <div className="bg-muted/50 border border-border rounded-lg p-4">
                  <pre className="text-sm text-foreground whitespace-pre-wrap overflow-x-auto">
                    {mcpTestToolModal.result}
                  </pre>
                </div>
              </div>
            )}

            {mcpTestToolModal.error && (
              <div className="mt-6">
                <h4 className="font-medium text-red-600 mb-2">Error:</h4>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-700">{mcpTestToolModal.error}</p>
                </div>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <Button
                variant="outline"
                onClick={closeMcpTestToolModal}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={executeMcpTool}
                disabled={mcpTestToolModal.testing}
                className="flex-1"
              >
                {mcpTestToolModal.testing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Testing...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Test Tool
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Tool Override Modal */}
      {showToolOverrideModal && overrideToolName && overrideServerId && overrideTool && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-lg w-full mx-4 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-foreground">
                Tool Override
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={closeToolOverrideModal}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="space-y-4">
              <div className="bg-muted/30 rounded-lg p-3 border border-border">
                <div className="text-xs text-muted-foreground mb-1">Original Tool</div>
                <div className="font-medium text-sm mb-1">{overrideTool?.name}</div>
                <div className="text-xs text-muted-foreground">{overrideTool?.description || 'No description'}</div>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Override Name
                </label>
                <Input
                  type="text"
                  value={overrideNameValue}
                  onChange={(e) => setOverrideNameValue(e.target.value)}
                  placeholder="Leave empty to use original name"
                  className="text-sm"
                />
                <div className="text-xs text-muted-foreground mt-1">
                  Override the tool name as it appears to the LLM
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Override Description
                </label>
                <textarea
                  value={overrideDescriptionValue}
                  onChange={(e) => setOverrideDescriptionValue(e.target.value)}
                  placeholder="Leave empty to use original description"
                  rows={3}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm"
                />
                <div className="text-xs text-muted-foreground mt-1">
                  Override the tool description as it appears to the LLM
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-6 pt-4 border-t border-border">
              <Button
                variant="outline"
                onClick={closeToolOverrideModal}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={saveToolOverride}
                disabled={savingOverride}
                className="flex-1"
              >
                {savingOverride ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    Save Override
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* HTTP Tool Importer */}
      {showHttpImporter && (
        <HttpToolImporter
          onImport={handleImportHttpTools}
          onClose={handleCancelHttpImporter}
        />
      )}

    </div>
  );
}