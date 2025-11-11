// components/PromptsTab.tsx

import { useState, useEffect } from 'react';
import { Plus, Trash2, X, Edit, Play, Loader2 } from 'lucide-react';
import { PromptIcon, McpIcon, VmcpIcon } from '@/lib/vmcp';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import VMCPMonacoEditor from '@/components/editor/VMCPMonacoEditor';
import { VMCPConfig } from '@/types/vmcp';
import { extractVariables, extractEnvironmentVariables, renameEnvironmentVariable } from '@/lib/vmcp';
import { cn } from '@/lib/utils';
// import { newApi, VMCPPromptRequest } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import type { VmcpPromptRequest as VMCPPromptRequest } from '@/api/generated/types.gen';
import { useToast } from '@/hooks/use-toast';


interface PromptsTabProps {
  vmcpConfig: VMCPConfig;
  servers: any[];
  addCustomPrompt: () => void;
  removeCustomPrompt: (index: number) => void;
  // getAllTools: () => any[];
  // getAllResources: () => any[];
  setVmcpConfig: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
  isRemoteVMCP?: boolean;
}

export default function PromptsTab({
  vmcpConfig,
  servers,
  addCustomPrompt,
  removeCustomPrompt,
  setVmcpConfig,
  isRemoteVMCP = false,
}: PromptsTabProps) {
  const [promptViewMode, setPromptViewMode] = useState<'list' | 'edit'>('list');
  const [selectedPromptIndex, setSelectedPromptIndex] = useState<number | null>(null);
  const [showModal, setShowModal] = useState(false);
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
  const [editingVariableIndex, setEditingVariableIndex] = useState<number | null>(null);


  // Test prompt states
  const [showTestPromptModal, setShowTestPromptModal] = useState(false);
  const [testPromptLoading, setTestPromptLoading] = useState(false);
  const [testPromptResult, setTestPromptResult] = useState<string | null>(null);
  const [testPromptError, setTestPromptError] = useState<string | null>(null);
  const [testPromptParameters, setTestPromptParameters] = useState<Record<string, string>>({});
  const [availablePrompts, setAvailablePrompts] = useState<any[]>([]);
  const [currentTestPrompt, setCurrentTestPrompt] = useState<any | null>(null);

  const { error } = useToast();


  console.log("Rendering PromptsTab with vmcpConfig");

  // MCP Server test states
  const [mcpTestPromptModal, setMcpTestPromptModal] = useState<{
    isOpen: boolean;
    prompt: any | null;
    serverId: string | null;
    formData: Record<string, any>;
    testing: boolean;
    result: string | null;
    error: string | null;
  }>({
    isOpen: false,
    prompt: null,
    serverId: null,
    formData: {},
    testing: false,
    result: null,
    error: null,
  });

  // Reset modal states when switching between prompts
  useEffect(() => {
    if (selectedPromptIndex !== null) {
      setShowModal(false);
      setShowVariableModal(false);
      setEditingIndex(null);
      setEditingVariableIndex(null);
    }
  }, [selectedPromptIndex]);

  const handleAddNewConfig = () => {
    console.log('Opening environment variable modal');
    setEditingIndex(null);
    setModalName('');
    setModalValue('');
    setModalDescription('');
    setModalRequired(false);
    setShowModal(true);
    setShowVariableModal(false); // Close variable modal if open
  };

  const handleEdit = (index: number) => {
    const envVar = vmcpConfig.environment_variables[index];
    setEditingIndex(index);
    setModalName(envVar.name);
    setModalValue(envVar.value);
    setModalDescription(envVar.description);
    setModalRequired(envVar.required);
    setShowModal(true);
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
          source: 'custom_prompt'
        }]
      }));
    }
    
    setShowModal(false);
  };

  const handleCancel = () => {
    setShowModal(false);
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
    setEditingVariableIndex(null);
    setShowVariableModal(true);
    setShowModal(false); // Close environment variable modal if open
  };

  const handleEditVariable = (index: number) => {
    if (selectedPromptIndex === null) return;
    
    const prompt = vmcpConfig.custom_prompts[selectedPromptIndex];
    if (!prompt.variables) prompt.variables = [];
    
    const variable = prompt.variables[index];
    setVariableModalType('edit');
    setVariableModalName(variable.name);
    setVariableModalDescription(variable.description || '');
    setVariableModalRequired(variable.required || false);
    setEditingVariableIndex(index);
    setShowVariableModal(true);
  };

  const handleSaveVariable = () => {
    if (!variableModalName.trim() || selectedPromptIndex === null) return;

    const prompt = vmcpConfig.custom_prompts[selectedPromptIndex];
    if (!prompt.variables) prompt.variables = [];

    if (variableModalType === 'edit' && editingVariableIndex !== null) {
      // Editing existing variable
      const oldName = prompt.variables[editingVariableIndex].name;
      const newName = variableModalName.trim();
      
      if (newName !== oldName) {
        // Rename variable in prompt text
        const newText = prompt.text.replace(new RegExp(`var\\(${oldName}\\)`, 'g'), `var(${newName})`);
        prompt.text = newText;
      }
      
      // Update the variable
      prompt.variables[editingVariableIndex] = {
        name: newName,
        description: variableModalDescription,
        required: variableModalRequired
      };
    } else {
      // Adding new variable
      prompt.variables.push({
        name: variableModalName.trim(),
        description: variableModalDescription,
        required: variableModalRequired
      });
      
    }
    
    // Update the VMCP config
    setVmcpConfig(prev => ({
      ...prev,
      custom_prompts: prev.custom_prompts.map((p, i) => 
        i === selectedPromptIndex ? prompt : p
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
    if (selectedPromptIndex === null) return;
    
    const prompt = vmcpConfig.custom_prompts[selectedPromptIndex];
    if (!prompt.variables) return;
    
    const variable = prompt.variables[index];
    
    // Remove var() syntax from prompt text
    prompt.text = prompt.text.replace(new RegExp(`var\\(${variable.name}\\)`, 'g'), '');
    
    // Remove the variable
    prompt.variables.splice(index, 1);
    
    // Update the VMCP config
    setVmcpConfig(prev => ({
      ...prev,
      custom_prompts: prev.custom_prompts.map((p, i) => 
        i === selectedPromptIndex ? prompt : p
      )
    }));
  };

  const handleTestPrompt = async () => {
    if (selectedPromptIndex === null) return;
    
    setTestPromptLoading(true);
    setTestPromptError(null);
    setTestPromptResult(null);
    
    try {
      const prompt = vmcpConfig.custom_prompts[selectedPromptIndex];
      const promptName = prompt.name;
      
      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available. Please log in again.');
      }
      
      // First, get the list of available prompts from the vMCP
      const promptsResult = await apiClient.listVMCPPrompts(vmcpConfig.id, accessToken);
      
      if (!promptsResult.success) {
        throw new Error(promptsResult.error || 'Failed to fetch prompts');
      }
      
      // Ensure promptsList is always an array - handle various response structures
      let promptsList: any[] = [];
      const responseData = promptsResult.data;
      
      if (Array.isArray(responseData)) {
        // Direct array response
        promptsList = responseData;
      } else if (responseData && typeof responseData === 'object') {
        // Try multiple possible nested structures
        if (Array.isArray(responseData.prompts)) {
          promptsList = responseData.prompts;
        } else if (Array.isArray(responseData.data?.prompts)) {
          promptsList = responseData.data.prompts;
        } else if (Array.isArray(responseData.data)) {
          promptsList = responseData.data;
        } else if (responseData.data && typeof responseData.data === 'object' && Array.isArray(responseData.data.data)) {
          promptsList = responseData.data.data;
        }
      }
      
      // Final safety check - ensure we have an array
      if (!Array.isArray(promptsList)) {
        console.warn('PromptsTab: Expected array but got:', typeof promptsList, promptsResult.data);
        promptsList = [];
      }
      
      setAvailablePrompts(promptsList);
      
      // Check if the prompt exists in the available prompts
      // Look for both the original name and the # prefixed name
      const foundPrompt = promptsList.find((p: any) => 
        p.name === promptName || p.name === `#${promptName}`
      );
      
      if (!foundPrompt) {
        setTestPromptError(`Prompt "${promptName}" not found in available prompts.`);
        setTestPromptLoading(false);
        return;
      }
      
      // Store the found prompt for the modal to use
      // Merge API response with local variables data
      const localPrompt = vmcpConfig.custom_prompts[selectedPromptIndex];
      const mergedPrompt = {
        ...foundPrompt,
        // Convert local variables to arguments format if not already present
        arguments: foundPrompt.arguments && foundPrompt.arguments.length > 0
          ? foundPrompt.arguments
          : localPrompt.variables && localPrompt.variables.length > 0
            ? localPrompt.variables.map(v => ({
                name: v.name,
                description: v.description || '',
                required: v.required || false
              }))
            : []
      };
      setCurrentTestPrompt(mergedPrompt);
      
      // Check if the prompt has parameters (from either source)
      const hasParameters = mergedPrompt.arguments && mergedPrompt.arguments.length > 0;
      
      if (hasParameters) {
        // Show modal for parameter input
        setTestPromptParameters({});
        setShowTestPromptModal(true);
        setTestPromptLoading(false);
      } else {
        // Execute prompt directly without parameters
        await executePrompt(promptName, {});
      }
      
    } catch (error) {
      console.error('Error testing prompt:', error);
      setTestPromptError(error instanceof Error ? error.message : 'An error occurred while testing the prompt');
      setTestPromptLoading(false);
    }
  };

  const executePrompt = async (promptName: string, parameters: Record<string, any>) => {
    setTestPromptLoading(true);
    setTestPromptError(null);
    setTestPromptResult(null);
    
    try {
      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available. Please log in again.');
      }
      
      // Create the prompt request with # prefix
      const promptRequest: VMCPPromptRequest = {
        prompt_id: `#${promptName}`,
        arguments: parameters
      };
      
      // Execute the prompt using newApi
      const result = await apiClient.getVMCPPrompt(vmcpConfig.id, promptRequest, accessToken);
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to execute prompt');
      }
      
      // Extract the result text from the response
      let resultText = '';
      if (result.data?.messages && result.data.messages.length > 0) {
        resultText = result.data.messages[0].content?.text || JSON.stringify(result.data.messages[0]);
      } else if (result.data?.content) {
        resultText = result.data.content;
      } else {
        resultText = JSON.stringify(result.data, null, 2);
      }
      
      setTestPromptResult(resultText);
      setShowTestPromptModal(false);
      setCurrentTestPrompt(null);
      
    } catch (error) {
      console.error('Error executing prompt:', error);
      setTestPromptError(error instanceof Error ? error.message : 'An error occurred while executing the prompt');
    } finally {
      setTestPromptLoading(false);
    }
  };

  const handleTestPromptSubmit = () => {
    if (selectedPromptIndex === null) return;
    
    const prompt = vmcpConfig.custom_prompts[selectedPromptIndex];
    executePrompt(prompt.name, testPromptParameters);
  };

  // MCP Server test functions
  const openMcpTestPromptModal = (prompt: any, serverId: string) => {
    console.log('Opening MCP test prompt modal for:', prompt.name, 'server:', serverId);
    const initialFormData: Record<string, any> = {};

    // Initialize form data based on prompt arguments
    const argumentsArray = Array.isArray(prompt.arguments)
      ? prompt.arguments
      : (prompt.arguments?.arguments && Array.isArray(prompt.arguments.arguments)
        ? prompt.arguments.arguments
        : []);

    if (argumentsArray.length > 0) {
      argumentsArray.forEach((arg: any) => {
        const argName = typeof arg === 'object' ? arg.name : arg;
        const defaultValue = typeof arg === 'object' && arg.default !== undefined ? arg.default : '';
        initialFormData[argName] = defaultValue;
      });
    }

    console.log('Setting modal state:', {
      isOpen: true,
      prompt,
      serverId,
      formData: initialFormData,
      testing: false,
    });

    setMcpTestPromptModal({
      isOpen: true,
      prompt,
      serverId,
      formData: initialFormData,
      testing: false,
      result: null,
      error: null,
    });
  };

  const closeMcpTestPromptModal = () => {
    setMcpTestPromptModal({
      isOpen: false,
      prompt: null,
      serverId: null,
      formData: {},
      testing: false,
      result: null,
      error: null,
    });
  };

  const handleMcpPromptFormChange = (key: string, value: any) => {
    setMcpTestPromptModal(prev => ({
      ...prev,
      formData: {
        ...prev.formData,
        [key]: value,
      },
    }));
  };

  const executeMcpPrompt = async () => {
    if (!mcpTestPromptModal.prompt || !mcpTestPromptModal.serverId) return;

    try {
      setMcpTestPromptModal(prev => ({ ...prev, testing: true }));

      // Get access token
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available. Please log in again.');
      }

      // Create the prompt request
      const promptRequest = {
        server_id: mcpTestPromptModal.serverId,
        prompt_name: mcpTestPromptModal.prompt.name,
        arguments: mcpTestPromptModal.formData
      };

      // Execute the prompt using apiClient
      const result = await apiClient.getMCPPrompt(mcpTestPromptModal.serverId!, promptRequest, accessToken);

      if (!result.success) {
        throw new Error(result.error || 'Failed to execute prompt');
      }

      // Extract the result text from the response
      let resultText = '';
      if (result.data?.messages && result.data.messages.length > 0) {
        resultText = result.data.messages[0].content?.text || JSON.stringify(result.data.messages[0]);
      } else if (result.data?.content) {
        resultText = result.data.content;
      } else {
        resultText = JSON.stringify(result.data, null, 2);
      }

      // Store the result in the modal state instead of closing
      setMcpTestPromptModal(prev => ({
        ...prev,
        result: resultText,
        error: null,
        testing: false,
      }));

    } catch (error) {
      console.error('Error executing MCP prompt:', error);
      setMcpTestPromptModal(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'An error occurred while executing the prompt',
        testing: false,
      }));
    }
  };

  if (promptViewMode === 'edit' && selectedPromptIndex !== null && vmcpConfig.custom_prompts[selectedPromptIndex]) {
    const prompt = vmcpConfig.custom_prompts[selectedPromptIndex];
    if (!prompt.variables) prompt.variables = [];
    
    return (
      <div>
        <div className="flex items-center justify-between gap-2 mb-4">
           
          <h2 className="flex-1 font-semibold text-foreground flex items-center gap-2">
            
            <PromptIcon className='h-4 w-4 text-primary'/>
            {isRemoteVMCP ? 'View Prompt' : 'Edit Prompt'}
            
          </h2>
            <Button
              size="sm"
              variant="outline"
              onClick={handleTestPrompt}
              disabled={testPromptLoading}
              className='text-xs text-primary'
            >
              {testPromptLoading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin text-primary" />
              ) : (
                <Play className="h-4 w-4 mr-2 text-primary" />
              )}
              Test Prompt
            </Button>
           <Button
              size="sm"
              variant="outline"
              onClick={() => {
                // Dont save empty prompt 
                if(vmcpConfig.custom_prompts[selectedPromptIndex].name.trim() === '') {
                  removeCustomPrompt(selectedPromptIndex);
                }
                setPromptViewMode('list');
                setShowModal(false);
                setShowVariableModal(false);
                setEditingIndex(null);
                setEditingVariableIndex(null);
              }}
            >
              <X className="h-4 w-4 text-primary"/>
            </Button>  
        </div>

        <div className="flex flex-col lg:flex-row gap-4">
          
          {/* Prompt Content */}
          <div className='flex-1 gap-16 min-w-2xl'>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">
                  Prompt Name
                </label>
                <Input
                  type="text"
                  disabled={isRemoteVMCP}
                  defaultValue={vmcpConfig.custom_prompts[selectedPromptIndex].name}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (/[^A-Za-z0-9_]/.test(value)) {
                      e.target.classList.add('border-red-500', 'focus:border-red-500');
                      const errorMsg = e.target.parentNode?.querySelector('.error-message');
                      if (errorMsg) {
                        errorMsg.textContent = 'Prompt name cannot contain spaces and special characters other than underscore';
                        errorMsg.classList.remove('hidden');
                      }
                      return;
                    } else {
                      e.target.classList.remove('border-red-500', 'focus:border-red-500');
                      const errorMsg = e.target.parentNode?.querySelector('.error-message');
                      if (errorMsg) {
                        errorMsg.classList.add('hidden');
                      }
                      vmcpConfig.custom_prompts[selectedPromptIndex].name = value;
                      setVmcpConfig(prev => ({
                        ...prev,
                        custom_prompts: [
                          ...prev.custom_prompts.slice(0, selectedPromptIndex),
                          {
                            ...prev.custom_prompts[selectedPromptIndex],
                            name: value
                          },
                          ...prev.custom_prompts.slice(selectedPromptIndex + 1)
                        ]
                      }));
                    }
                  }}
                  placeholder="Enter prompt name (no spaces or special characters other than underscore)"
                />
                <div className="error-message hidden text-accent text-sm mt-1">
                  Prompt name cannot contain spaces or special characters other than underscore
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">
                  Description
                </label>
                <Input
                  type="text"
                  disabled={isRemoteVMCP}
                  defaultValue={vmcpConfig.custom_prompts[selectedPromptIndex].description}
                  onChange={(e) => {
                      vmcpConfig.custom_prompts[selectedPromptIndex].description = e.target.value;
                      setVmcpConfig(prev => ({
                        ...prev,
                        custom_prompts: [
                          ...prev.custom_prompts.slice(0, selectedPromptIndex),
                          {
                            ...prev.custom_prompts[selectedPromptIndex],
                            description: e.target.value
                          },
                          ...prev.custom_prompts.slice(selectedPromptIndex + 1)
                        ]
                      }));
                  }}
                  placeholder="What does this prompt do?"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-muted-foreground">
                    Prompt Text <span className='text-accent'>(use @ to mention params, config, tools and resources)</span>
                  </label>
                  
                </div>
                <VMCPMonacoEditor
                  value={vmcpConfig.custom_prompts[selectedPromptIndex].text}
                  readOnly={isRemoteVMCP}
                  onChange={(text) => {
                    //console.log("Text changed ==========", text);
                      vmcpConfig.custom_prompts[selectedPromptIndex].text = text;
                      setVmcpConfig(prev => ({
                        ...prev,
                        custom_prompts: [
                          ...prev.custom_prompts.slice(0, selectedPromptIndex),
                          {
                            ...prev.custom_prompts[selectedPromptIndex],
                            text
                          },
                          ...prev.custom_prompts.slice(selectedPromptIndex + 1)
                        ]
                      }));
                  }}
                  height={300}
                  vmcpConfig={vmcpConfig}
                  editKey="custom_prompt"
                  editIndex={selectedPromptIndex}
                  setVmcpConfig={setVmcpConfig}
                />
              </div>
            </div>
          </div>
          
          {/* Variables */}
          <div className='flex gap-2 basis-sm flex-col'>
            {/* Parameters Display */}
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
                {prompt.variables && prompt.variables.length > 0 ? (
                  prompt.variables.map((variable, varIndex) => (
                    <div key={`prompt-var-${selectedPromptIndex}-${varIndex}-${variable.name}`} className="rounded-lg p-3 border border-border">
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <div className="flex-1">
                          <span className="text-sm font-medium text-foreground">{variable.name}</span>
                          <div className="text-xs text-muted-foreground mt-1">
                            {variable.description || 'No description'}
                          </div>
                        </div>
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
                      <div className="flex items-center">
                        <span className={`text-xs px-2 py-1 rounded ${
                          variable.required 
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

            {/* Config Display */}
            {/* <div className="bg-card p-2 rounded-2xl">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium underline underline-offset-4 decoration-accent text-foreground">Config</h4>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleAddNewConfig}
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
      
      {/* Add/Edit Modal */}
      {showModal && (
       <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
       <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-lg">
         <h3 className="text-lg font-semibold text-foreground mb-4">
              {editingIndex !== null ? 'Edit Config Variable' : 'Add Config Variable'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Variable Name
                </label>
                <Input
                  type="text"
                  value={modalName}
                  onChange={(e) => setModalName(e.target.value)}
                  placeholder="VARIABLE_NAME"
                  className="font-mono"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Description
                </label>
                <Input
                  type="text"
                  value={modalDescription}
                  onChange={(e) => setModalDescription(e.target.value)}
                  placeholder="What is this variable for?"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Value
                </label>
                <Input
                  type="text"
                  value={modalValue}
                  onChange={(e) => setModalValue(e.target.value)}
                  placeholder="Variable value (optional)"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="env-required"
                  checked={modalRequired}
                  onCheckedChange={(checked: boolean) => setModalRequired(checked)}
                />
                <Label htmlFor="env-required" className="text-sm font-medium">
                  Required
                </Label>
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button
                variant="outline"
                onClick={handleCancel}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={!modalName.trim()}
                className="flex-1"
              >
                {editingIndex !== null ? 'Update' : 'Add'}
              </Button>
            </div>
          </div>
        </div>
      )}

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
                disabled={!variableModalName.trim() || selectedPromptIndex === null}
                className="flex-1"
              >
                {editingVariableIndex !== null ? 'Update' : 'Add'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Test Prompt Modal */}
      {showTestPromptModal && selectedPromptIndex !== null && currentTestPrompt && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-2xl w-full mx-4 shadow-lg max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Test Prompt: #{vmcpConfig.custom_prompts[selectedPromptIndex].name}
            </h3>
            
            <div className="space-y-4">
              <div className="text-sm text-muted-foreground mb-4">
                {currentTestPrompt.description || 'No description available'}
              </div>
              
              {currentTestPrompt.arguments && currentTestPrompt.arguments.length > 0 ? (
                <div className="space-y-4">
                  <h4 className="font-medium text-foreground">Parameters:</h4>
                  {currentTestPrompt.arguments.map((arg: any, index: number) => (
                    <div key={index} className="space-y-2">
                      <label className="block text-sm font-medium text-foreground">
                        {arg.name}
                        {arg.required && <span className="text-red-500 ml-1">*</span>}
                      </label>
                      <Input
                        type="text"
                        value={testPromptParameters[arg.name] || ''}
                        onChange={(e) => setTestPromptParameters(prev => ({
                          ...prev,
                          [arg.name]: e.target.value
                        }))}
                        placeholder={arg.description || `Enter ${arg.name}`}
                      />
                      {arg.description && (
                        <p className="text-xs text-muted-foreground">{arg.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  This prompt has no parameters.
                </div>
              )}
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button
                variant="outline"
                onClick={() => {
                  setShowTestPromptModal(false);
                  setTestPromptParameters({});
                  setCurrentTestPrompt(null);
                }}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleTestPromptSubmit}
                disabled={testPromptLoading}
                className="flex-1"
              >
                {testPromptLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Testing...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Test Prompt
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Test Prompt Result Display */}
      {(testPromptResult || testPromptError) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-4xl w-full mx-4 shadow-lg max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-foreground">
                Test Prompt Result
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setTestPromptResult(null);
                  setTestPromptError(null);
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            {testPromptError ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <h4 className="font-medium text-red-800 mb-2">Error:</h4>
                <p className="text-red-700 text-sm">{testPromptError}</p>
              </div>
            ) : (
              <div className="bg-muted/50 border border-border rounded-lg p-4">
                <h4 className="font-medium text-foreground mb-2">Result:</h4>
                <pre className="text-sm text-foreground whitespace-pre-wrap overflow-x-auto">
                  {testPromptResult}
                </pre>
              </div>
            )}
            
            <div className="flex justify-end mt-6">
              <Button
                onClick={() => {
                  setTestPromptResult(null);
                  setTestPromptError(null);
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
      <Tabs defaultValue="custom-prompts" className="w-full">
        <TabsList className="mb-4 bg-transparent p-0 h-auto justify-start w-full border-b-1">
          <TabsTrigger 
            value="custom-prompts"
            className="data-[state=active]:bg-background data-[state=active]:border-accent data-[state=active]:border-b-1 data-[state=active]:border-t-0 data-[state=active]:border-l-0 data-[state=active]:border-r-0 rounded-none"
          >
            <VmcpIcon className="h-4 w-4" />
            vMCP Prompts
            <Badge variant="outline" className="ml-2 text-xs">
              {vmcpConfig.custom_prompts.length}
            </Badge>
          </TabsTrigger>
          {vmcpConfig.vmcp_config.selected_servers.map((server) => {
            const fullServer = servers.find(s => s.id === server.server_id);
            const selectedPrompts = vmcpConfig.vmcp_config.selected_prompts[server.server_id] || [];
            
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
                  {selectedPrompts.length}/{server?.prompt_details?.length || 0}
                </Badge>
              </TabsTrigger>
            );
          })}
        </TabsList>
        
        <TabsContent value="custom-prompts">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-muted-foreground">Select a prompt to edit or create a new one</p>
              <Button
                size="sm"
                variant={'outline'}
                onClick={() => {  
                  addCustomPrompt();
                  setSelectedPromptIndex(vmcpConfig.custom_prompts.length);
                  setPromptViewMode('edit');
                }}
                disabled={isRemoteVMCP}
                title={isRemoteVMCP ? 'Adding prompts disabled for remote vMCPs' : ''}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Prompt
              </Button>
            </div>

            {vmcpConfig.custom_prompts.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No prompts created yet. Click "Add Prompt" to create your first prompt.
              </div>
            ) : (
              <div className="grid gap-4">
                {vmcpConfig.custom_prompts.map((prompt, index) => (
                  <div
                    key={`prompt-list-${index}-${prompt.name || 'unnamed'}`}
                    className="bg-card rounded-lg p-4 border border-border hover:border-primary cursor-pointer transition-colors"
                    onClick={() => {
                      setSelectedPromptIndex(index);
                      setPromptViewMode('edit');
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h3 className="font-medium text-foreground">{prompt.name || `Prompt ${index + 1}`}</h3>
                        <p className="text-sm text-muted-foreground">{prompt.description || 'No description'}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {prompt.text ? `${prompt.text.substring(0, 100)}${prompt.text.length > 100 ? '...' : ''}` : 'No content'}
                        </p>
                      </div>
                      {!isRemoteVMCP && (
                        <Button
                          size="sm"
                          title={isRemoteVMCP ? 'Deleting prompts disabled for remote vMCPs' : ''}
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                          removeCustomPrompt(index);
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
          // If the server doesn't have prompt_details, try to find it in the servers context
          if (!fullServer.prompt_details && servers) {
            fullServer = servers.find(s => s.server_id === server.server_id) || server;
          }
          const serverPrompts = fullServer?.prompt_details || [];
          const selectedPrompts = vmcpConfig.vmcp_config.selected_prompts[server.server_id] || [];
          
          return (
            <TabsContent key={server.server_id} value={`server-${server.server_id}`}>
              <div className="space-y-4">

                <div className="flex w-full items-center place-content-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const allPromptNames = serverPrompts.map((p: any) => p.name);
                      setVmcpConfig(prev => ({
                        ...prev,
                        vmcp_config: {
                          ...prev.vmcp_config,
                          selected_prompts: {
                            ...prev.vmcp_config.selected_prompts,
                            [server.server_id]: allPromptNames
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
                          selected_prompts: {
                            ...prev.vmcp_config.selected_prompts,
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
                
                {serverPrompts.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                      <PromptIcon className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <h4 className="text-base font-medium text-foreground mb-1">No Prompts Available</h4>
                    <p className="text-sm text-muted-foreground">This MCP server doesn't expose any prompts.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {serverPrompts.map((prompt: any) => {
                      const hasArguments = prompt.arguments && (
                        Array.isArray(prompt.arguments) ? prompt.arguments.length > 0 :
                        prompt.arguments.arguments && Array.isArray(prompt.arguments.arguments) && prompt.arguments.arguments.length > 0
                      );
                      
                      return (
                        <div
                          key={prompt.name}
                          className={cn(
                            "p-3 rounded-lg border transition-all duration-200 cursor-pointer",
                            selectedPrompts.includes(prompt.name)
                              ? "bg-muted/60 border-primary/50 hover:border-primary/30"
                              : "bg-muted/40 border-border/60 hover:bg-muted/60 hover:border-border/80"
                          )}
                          onClick={() => {
                             if (isRemoteVMCP) {
                              //Show error toast
                              error("Selection disabled for community vMCPs", {
                                        description: "Extend the vMCP to make changes"});
                              return; // Disable selection for remote vMCPs
                            }
                            const newSelected = new Set(selectedPrompts);
                            if (newSelected.has(prompt.name)) {
                              newSelected.delete(prompt.name);
                            } else {
                              newSelected.add(prompt.name);
                            }
                            setVmcpConfig(prev => ({
                              ...prev,
                              vmcp_config: {
                                ...prev.vmcp_config,
                                selected_prompts: {
                                  ...prev.vmcp_config.selected_prompts,
                                  [server.server_id]: Array.from(newSelected)
                                }
                              }
                            }));
                          }}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <PromptIcon className="h-4 w-4 text-primary" />
                              <span className="font-medium text-sm">{prompt.name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  console.log('Test button clicked for prompt:', prompt.name);
                                  e.stopPropagation();
                                  openMcpTestPromptModal(prompt, server.server_id);
                                }}
                                className="h-6 px-2 text-xs opacity-60 hover:opacity-100 transition-opacity"
                              >
                                <Play className="h-3 w-3 mr-1" />
                                Test
                              </Button>
                              <div className={cn(
                                "w-4 h-4 rounded-full border-2 flex items-center justify-center",
                                selectedPrompts.includes(prompt.name)
                                  ? "bg-primary border-primary"
                                  : "border-border"
                              )}>
                                {selectedPrompts.includes(prompt.name) && (
                                  <div className="w-2 h-2 bg-primary-foreground rounded-full"></div>
                                )}
                              </div>
                            </div>
                          </div>
                          {prompt.description && (
                            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{prompt.description}</p>
                          )}
                          {/* {hasArguments && (
                            <div className="mt-2">
                              <Badge variant="outline" className="text-xs">
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
              <p className="text-sm text-muted-foreground">Add MCP servers in the MCP Servers tab to see their prompts here.</p>
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* MCP Test Prompt Modal */}
      {mcpTestPromptModal.isOpen && mcpTestPromptModal.prompt && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-2xl w-full mx-4 shadow-lg max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Test MCP Prompt: {mcpTestPromptModal.prompt.name}
            </h3>
            
            <div className="space-y-4">
              <div className="text-sm text-muted-foreground mb-4">
                {mcpTestPromptModal.prompt.description || 'No description available'}
              </div>
              
              {(() => {
                const argumentsArray = Array.isArray(mcpTestPromptModal.prompt.arguments)
                  ? mcpTestPromptModal.prompt.arguments
                  : (mcpTestPromptModal.prompt.arguments?.arguments && Array.isArray(mcpTestPromptModal.prompt.arguments.arguments)
                    ? mcpTestPromptModal.prompt.arguments.arguments
                    : []);
                
                if (argumentsArray.length > 0) {
                  return (
                    <div className="space-y-4">
                      <h4 className="font-medium text-foreground">Parameters:</h4>
                      {argumentsArray.map((arg: any, index: number) => (
                        <div key={index} className="space-y-2">
                          <label className="block text-sm font-medium text-foreground">
                            {typeof arg === 'object' ? arg.name : arg}
                            {typeof arg === 'object' && arg.required && <span className="text-red-500 ml-1">*</span>}
                          </label>
                          <Input
                            type="text"
                            value={mcpTestPromptModal.formData[typeof arg === 'object' ? arg.name : arg] || ''}
                            onChange={(e) => handleMcpPromptFormChange(typeof arg === 'object' ? arg.name : arg, e.target.value)}
                            placeholder={typeof arg === 'object' && arg.description ? arg.description : `Enter ${typeof arg === 'object' ? arg.name : arg}`}
                          />
                          {typeof arg === 'object' && arg.description && (
                            <p className="text-xs text-muted-foreground">{arg.description}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                } else {
                  return (
                    <div className="text-sm text-muted-foreground">
                      This prompt has no parameters.
                    </div>
                  );
                }
              })()}
            </div>
            
            {/* Result Display */}
            {mcpTestPromptModal.result && (
              <div className="mt-6">
                <h4 className="font-medium text-foreground mb-2">Result:</h4>
                <div className="bg-muted/50 border border-border rounded-lg p-4">
                  <pre className="text-sm text-foreground whitespace-pre-wrap overflow-x-auto">
                    {mcpTestPromptModal.result}
                  </pre>
                </div>
              </div>
            )}
            
            {mcpTestPromptModal.error && (
              <div className="mt-6">
                <h4 className="font-medium text-red-600 mb-2">Error:</h4>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-700">{mcpTestPromptModal.error}</p>
                </div>
              </div>
            )}
            
            <div className="flex gap-3 mt-6">
              <Button
                variant="outline"
                onClick={closeMcpTestPromptModal}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={executeMcpPrompt}
                disabled={mcpTestPromptModal.testing}
                className="flex-1"
              >
                {mcpTestPromptModal.testing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Testing...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Test Prompt
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}