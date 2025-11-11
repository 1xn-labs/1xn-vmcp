
import React, { useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from "react";
import { VMCPConfig } from '@/types/vmcp';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

// Lazy-load Monaco React for better performance
const MonacoEditorComponent = lazy(() => import("@monaco-editor/react"));

// Wrapper to match the expected interface
const MonacoEditor = (props: any) => (
  <Suspense fallback={<div className="w-full h-full flex items-center justify-center">Loading editor...</div>}>
    <MonacoEditorComponent {...props} />
  </Suspense>
);

export interface VMCPMonacoEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string | number;
  className?: string;
  vmcpConfig?: VMCPConfig;
  editKey?: "system_prompt" | "custom_prompt" | "custom_tool";
  editIndex?: number | null;
  readOnly?: boolean;
  // Optional explicit language for syntax highlighting (e.g., 'python', 'json')
  language?: string;
  // Whether to show the VMCP syntax guide (default: true)
  showSyntaxGuide?: boolean;
  // Function to update the VMCP config (required for atomic blocks persistence)
  setVmcpConfig?: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
}

interface AtomicBlock {
  id: string;
  startLine: number;
  startColumn: number;
  endLine: number;
  endColumn: number;
  type: 'tool' | 'prompt' | 'resource' | 'env' | 'var';
  server?: string;
  serverId?: string;
  name: string;
  text: string;
  data?: any;
  parameters?: Record<string, any>;
}

interface ParameterModalProps {
  isOpen: boolean;
  onClose: () => void;
  block: AtomicBlock | null;
  onSave: (parameters: Record<string, any>) => void;
}

interface TestResult {
  success: boolean;
  result?: any;
  error?: string;
  timestamp: string;
}

interface CompletionItem {
  completion: string;
  label: string;
  description: string;
  kind: string;
  server?: string;
  serverId?: string;
  toolData?: any;
  promptData?: any;
}

// Helper function to get Pydantic-style datatype string
function getDatatypeString(schema: any): string {
  if (!schema || !schema.type) return 'str';
  
  switch (schema.type) {
    case 'string':
      return 'str';
    case 'number':
    case 'integer':
      return 'int';
    case 'boolean':
      return 'bool';
    case 'array':
      if (schema.items?.type) {
        const itemType = getDatatypeString({ type: schema.items.type });
        return `[${itemType}]`;
      }
      return '[str]';
    case 'object':
      return 'dict';
    default:
      return 'str';
  }
}

// Build tool snippet with proper parameter handling and datatype hints
function buildToolSnippet(toolData: any): string {
  if (!toolData?.inputSchema?.properties) {
    return `${toolData.label}()`;
  }
  
  const properties = toolData.inputSchema.properties;
  const required = toolData.inputSchema.required || [];
  const paramNames = Object.keys(properties);
  
  if (paramNames.length === 0) {
    return `${toolData.label}()`;
  }
  
  const paramsSnippet = paramNames
    .map((paramName, index) => {
      const schema = properties[paramName] || {};
      const isRequired = required.includes(paramName);
      const isString = schema.type === "string" || !schema.type;
      const defaultValue = schema.default || (isString ? "" : "null");
      const placeholder = schema.description || paramName;
      const datatype = getDatatypeString(schema);
      
      if (isString) {
        return `${paramName}: ${datatype} = "\${${index + 1}:${placeholder}}"`;
      }
      return `${paramName}: ${datatype} = \${${index + 1}:${defaultValue}}`;
    })
    .join(", ");
    
  return `${toolData.label}(${paramsSnippet})`;
}

// Build prompt snippet with proper parameter handling
function buildPromptSnippet(promptData: any): string {
  if (!promptData?.arguments) {
    return `${promptData.label}()`;
  }
  
  const args = promptData.arguments;
  const paramNames = args.map((arg: any) => arg.name);
  
  if (paramNames.length === 0) {
    return `${promptData.label}()`;
  }
  
  const paramsSnippet = args
    .map((arg: any, index: number) => {
      const paramName = arg.name;
      const isRequired = arg.required !== false; // Default to required if not specified
      const description = arg.description || paramName;
      const isString = true; // Prompts typically use string parameters
      
      if (isString) {
        return `${paramName}="\${${index + 1}:${description}}"`;
      }
      return `${paramName}=\${${index + 1}:${description}}`;
    })
    .join(", ");
    
  return `${promptData.label}(${paramsSnippet})`;
}

// Parameter Modal Component
const ParameterModal: React.FC<ParameterModalProps> = ({ isOpen, onClose, block, onSave }) => {
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    if (block?.parameters) {
      setParameters(block.parameters);
    } else {
      setParameters({});
    }
    // Clear test result when block changes
    setTestResult(null);
  }, [block]);

  if (!isOpen || !block) return null;

  const handleTest = async () => {
    if (!block) return;
    
    setIsTesting(true);
    setTestResult(null);
    
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      let result: any;
      
      if (block.type === 'tool') {
        // Test tool call
        const serverId = block.serverId || 'custom';
        // Extract just the tool name (remove server prefix if present)
        const toolName = block.name.includes('.') ? block.name.split('.').pop() || block.name : block.name;
        
        console.log(`🧪 [VMCPEditor] Testing tool:`, {
          toolName,
          serverId,
          server: block.server,
          parameters
        });
        
        result = await apiClient.callMCPTool(serverId, {
          tool_name: toolName,
          arguments: parameters,
        }, accessToken);
      } else if (block.type === 'prompt') {
        // Test prompt call
        const serverId = block.serverId || 'custom';
        // Extract just the prompt name (remove server prefix if present)
        const promptName = block.name.includes('.') ? block.name.split('.').pop() || block.name : block.name;
        
        console.log(`🧪 [VMCPEditor] Testing prompt:`, {
          promptName,
          serverId,
          server: block.server,
          parameters
        });
        
        result = await apiClient.getMCPPrompt(serverId, {
          prompt_name: promptName,
          arguments: parameters,
        }, accessToken);
      } else {
        throw new Error('Unsupported block type for testing');
      }

      const testResult: TestResult = {
        success: result.success,
        result: result.data,
        error: result.error,
        timestamp: new Date().toISOString(),
      };

      setTestResult(testResult);
    } catch (error) {
      console.error('Test failed:', error);
      const testResult: TestResult = {
        success: false,
        error: error instanceof Error ? error.message : 'Test failed - check server connection and parameters',
        timestamp: new Date().toISOString(),
      };
      setTestResult(testResult);
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = () => {
    // Validate required parameters
    let hasErrors = false;
    const errors: string[] = [];
    
    if (block.type === 'tool' && block.data?.inputSchema?.properties) {
      const required = block.data.inputSchema.required || [];
      const properties = block.data.inputSchema.properties;
      
      required.forEach((paramName: string) => {
        const paramValue = parameters[paramName];
        const paramSchema = properties[paramName];
        const paramType = paramSchema?.type || 'string';
        
        // Check if parameter is missing or empty
        if (paramValue === undefined || paramValue === null || paramValue === '') {
          hasErrors = true;
          errors.push(`${paramName} is required`);
        } else if (paramType === 'array' && (!Array.isArray(paramValue) || paramValue.length === 0)) {
          hasErrors = true;
          errors.push(`${paramName} is required and must contain at least one item`);
        }
      });
    }
    
    if (block.type === 'prompt' && block.data?.arguments) {
      block.data.arguments.forEach((arg: any) => {
        if (arg.required !== false && (!parameters[arg.name] || parameters[arg.name] === '')) {
          hasErrors = true;
          errors.push(`${arg.name} is required`);
        }
      });
    }
    
    if (hasErrors) {
      // Show validation errors (you could add a toast or error state here)
      console.warn('Validation errors:', errors);
      return;
    }
    
    onSave(parameters);
    onClose();
  };

  // Simple JSON Editor component
  const JsonEditor: React.FC<{
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  }> = ({ value, onChange, placeholder = "Enter valid JSON" }) => {
    const [validationMessage, setValidationMessage] = useState('');

    const validateJson = () => {
      if (!value.trim()) {
        setValidationMessage('✓ Empty JSON is valid');
        return;
      }

      try {
        JSON.parse(value);
        setValidationMessage('✓ Valid JSON');
      } catch (error) {
        setValidationMessage(`✗ Invalid JSON: ${error instanceof Error ? error.message : 'Parse error'}`);
      }
    };

    const formatJson = () => {
      if (!value.trim()) return;
      
      try {
        const parsed = JSON.parse(value);
        const formatted = JSON.stringify(parsed, null, 2);
        onChange(formatted);
        setValidationMessage('✓ Formatted JSON');
      } catch (error) {
        setValidationMessage(`✗ Cannot format: ${error instanceof Error ? error.message : 'Parse error'}`);
      }
    };

    return (
      <div className="space-y-2">
        {/* Top bar with buttons */}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={formatJson}
            className="px-2 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600"
            title="Format JSON"
          >
            📝 Format
          </button>
          <button
            type="button"
            onClick={validateJson}
            className="px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600"
            title="Validate JSON"
          >
            ✓ Validate
          </button>
        </div>
        
        {/* JSON textarea */}
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="json-editor w-full px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm min-h-[120px] resize-y"
          placeholder={placeholder}
          spellCheck={false}
          style={{
            fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
            lineHeight: '1.4',
            tabSize: 2
          }}
        />
        
        {/* Validation message */}
        {validationMessage && (
          <p className={`text-xs ${validationMessage.startsWith('✓') ? 'text-green-600' : 'text-red-500'}`}>
            {validationMessage}
          </p>
        )}
      </div>
    );
  };

  // Array input component
  const ArrayInput: React.FC<{
    paramName: string;
    schema: any;
    value: any[];
    onChange: (value: any[]) => void;
    isRequired: boolean;
  }> = ({ paramName, schema, value, onChange, isRequired }) => {
    const [newItem, setNewItem] = useState('');
    const [newItemError, setNewItemError] = useState('');
    const [editingIndex, setEditingIndex] = useState<number | null>(null);
    const [editingValue, setEditingValue] = useState('');

    const itemType = schema.items?.type || 'string';
    const itemDescription = schema.items?.description || '';

    const parseValue = (inputValue: string): { value: any; error: string } => {
      if (!inputValue.trim()) {
        return { value: null, error: 'Item cannot be empty' };
      }

      let parsedValue: any = inputValue.trim();
      
      try {
        if (itemType === 'number' || itemType === 'integer') {
          parsedValue = parseFloat(inputValue);
          if (isNaN(parsedValue)) {
            return { value: null, error: 'Must be a valid number' };
          }
          if (itemType === 'integer' && !Number.isInteger(parsedValue)) {
            return { value: null, error: 'Must be a valid integer' };
          }
        } else if (itemType === 'boolean') {
          if (inputValue.toLowerCase() === 'true') {
            parsedValue = true;
          } else if (inputValue.toLowerCase() === 'false') {
            parsedValue = false;
          } else {
            return { value: null, error: 'Must be "true" or "false"' };
          }
        } else if (itemType === 'object') {
          parsedValue = JSON.parse(inputValue);
        }
        // For string type, use the value as-is
      } catch (error) {
        return { value: null, error: `Invalid ${itemType} format` };
      }

      return { value: parsedValue, error: '' };
    };

    const addItem = () => {
      const { value: parsedValue, error } = parseValue(newItem);
      
      if (error) {
        setNewItemError(error);
        return;
      }

      setNewItemError('');
      setNewItem('');
      onChange([...value, parsedValue]);
    };

    const startEditing = (index: number) => {
      const item = value[index];
      setEditingIndex(index);
      if (typeof item === 'object') {
        setEditingValue(JSON.stringify(item, null, 2));
      } else {
        setEditingValue(String(item));
      }
    };

    const saveEdit = () => {
      if (editingIndex === null) return;

      const { value: parsedValue, error } = parseValue(editingValue);
      
      if (error) {
        setNewItemError(error);
        return;
      }

      const newValue = [...value];
      newValue[editingIndex] = parsedValue;
      onChange(newValue);
      
      setEditingIndex(null);
      setEditingValue('');
      setNewItemError('');
    };

    const cancelEdit = () => {
      setEditingIndex(null);
      setEditingValue('');
      setNewItemError('');
    };

    const removeItem = (index: number) => {
      onChange(value.filter((_, i) => i !== index));
    };

    const getItemDisplayValue = (item: any) => {
      if (typeof item === 'string') {
        return item; // Don't add quotes around strings
      } else if (typeof item === 'object') {
        return JSON.stringify(item, null, 2);
      }
      return String(item);
    };

    const getInputType = () => {
      if (itemType === 'number' || itemType === 'integer') return 'number';
      if (itemType === 'boolean') return 'text';
      if (itemType === 'object') return 'text';
      return 'text';
    };

    const getPlaceholder = () => {
      if (itemType === 'number' || itemType === 'integer') return 'Enter a number';
      if (itemType === 'boolean') return 'Enter "true" or "false"';
      if (itemType === 'object') return 'Enter valid JSON object';
      return 'Enter text';
    };

    return (
      <div className="space-y-3">
        {/* Current items */}
        {value.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">Current items:</p>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {value.map((item, index) => (
                <div key={index} className="space-y-2">
                  {editingIndex === index ? (
                    // Editing mode
                    <div className="p-3 bg-blue-50 dark:bg-blue-950/20 rounded border border-blue-200 dark:border-blue-800">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-muted-foreground">#{index + 1} - Editing</span>
                      </div>
                      
                      {itemType === 'object' ? (
                        <JsonEditor
                          value={editingValue}
                          onChange={setEditingValue}
                          placeholder="Enter valid JSON object"
                        />
                      ) : (
                        <input
                          type={getInputType()}
                          value={editingValue}
                          onChange={(e) => setEditingValue(e.target.value)}
                          className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm"
                          placeholder={getPlaceholder()}
                        />
                      )}
                      
                      <div className="flex gap-2 mt-2">
                        <button
                          type="button"
                          onClick={saveEdit}
                          className="px-3 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="px-3 py-1 bg-gray-500 text-white rounded text-xs hover:bg-gray-600"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    // Display mode
                    <div className="flex items-center gap-2 p-2 bg-muted/50 rounded border">
                      <span className="text-xs text-muted-foreground">#{index + 1}</span>
                      <code className="flex-1 text-xs bg-background px-2 py-1 rounded border">
                        {getItemDisplayValue(item)}
                      </code>
                      <button
                        type="button"
                        onClick={() => startEditing(index)}
                        className="text-blue-500 hover:text-blue-700 text-xs px-2 py-1 rounded hover:bg-blue-50 dark:hover:bg-blue-950/20"
                        title="Edit item"
                      >
                        ✏️
                      </button>
                      <button
                        type="button"
                        onClick={() => removeItem(index)}
                        className="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-950/20"
                        title="Remove item"
                      >
                        ✕
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Add new item */}
        <div className="space-y-2">
          {itemType === 'object' ? (
            <JsonEditor
              value={newItem}
              onChange={setNewItem}
              placeholder="Enter valid JSON object"
            />
          ) : (
            <input
              type={getInputType()}
              value={newItem}
              onChange={(e) => {
                setNewItem(e.target.value);
                setNewItemError('');
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addItem();
                }
              }}
              className={`w-full px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm ${
                newItemError ? 'border-red-500' : ''
              }`}
              placeholder={getPlaceholder()}
            />
          )}
          
          <div className="flex gap-2">
            <button
              type="button"
              onClick={addItem}
              className="px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm font-medium"
              title="Add item to array"
            >
              Add
            </button>
          </div>
          
          {newItemError && (
            <p className="text-xs text-red-500">{newItemError}</p>
          )}
          
          {itemDescription && (
            <p className="text-xs text-muted-foreground">
              Item type: {itemType} - {itemDescription}
            </p>
          )}
        </div>

        {/* Array info */}
        <div className="text-xs text-muted-foreground">
          <p>Array of {itemType} items ({value.length} items)</p>
        </div>
      </div>
    );
  };

  const getParameterFields = () => {
    if (block.type === 'tool' && block.data?.inputSchema?.properties) {
      const properties = block.data.inputSchema.properties;
      const required = block.data.inputSchema.required || [];
      
      return Object.entries(properties).map(([paramName, schema]: [string, any]) => {
        const isRequired = required.includes(paramName);
        const paramType = schema.type || 'string';
        const paramDesc = schema.description || 'No description';
        const defaultValue = schema.default || '';
        
        return (
          <div key={paramName} className="space-y-2">
            <label className="block text-sm font-medium">
              <span className="flex items-center gap-2">
                {paramName}
                {isRequired && <span className="text-red-500 text-lg">*</span>}
                <span className="text-xs text-muted-foreground">({paramType})</span>
              </span>
            </label>
            {paramDesc !== 'No description' && (
              <p className="text-xs text-muted-foreground">{paramDesc}</p>
            )}
            
            {paramType === 'array' ? (
              <ArrayInput
                paramName={paramName}
                schema={schema}
                value={parameters[paramName] || []}
                onChange={(value) => setParameters(prev => ({ ...prev, [paramName]: value }))}
                isRequired={isRequired}
              />
            ) : paramType === 'object' ? (
              <div className="space-y-2">
                {/* Validate Button */}
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => {
                      const currentValue = parameters[paramName] || '';
                      if (!currentValue.trim()) {
                        setParameters(prev => ({ ...prev, [`${paramName}_validation`]: '✓ Empty JSON is valid' }));
                        return;
                      }
                      try {
                        JSON.parse(currentValue);
                        setParameters(prev => ({ ...prev, [`${paramName}_validation`]: '✓ Valid JSON' }));
                      } catch (error) {
                        setParameters(prev => ({ ...prev, [`${paramName}_validation`]: `✗ Invalid JSON: ${error instanceof Error ? error.message : 'Parse error'}` }));
                      }
                    }}
                    className="px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600"
                    title="Validate JSON"
                  >
                    ✓ Validate
                  </button>
                </div>
                
                {/* Textarea */}
                <textarea
                  value={parameters[paramName] || ''}
                  onChange={(e) => {
                    const textWithoutNewlines = e.target.value.replace(/\n/g, '');
                    setParameters(prev => ({ ...prev, [paramName]: textWithoutNewlines }));
                  }}
                  className="json-editor w-full px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm min-h-[120px] resize-y"
                  placeholder="Enter valid JSON object"
                  spellCheck={false}
                  style={{
                    fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
                    lineHeight: '1.4',
                    tabSize: 2
                  }}
                />
                
                {/* Validation Message */}
                {parameters[`${paramName}_validation`] && (
                  <p className={`text-xs ${parameters[`${paramName}_validation`].startsWith('✓') ? 'text-green-600' : 'text-red-500'}`}>
                    {parameters[`${paramName}_validation`]}
                  </p>
                )}
              </div>
            ) : (
              <input
                type={paramType === 'number' ? 'number' : paramType === 'boolean' ? 'checkbox' : 'text'}
                value={parameters[paramName] || defaultValue}
                onChange={(e) => {
                  const value = paramType === 'boolean' ? e.target.checked : e.target.value;
                  setParameters(prev => ({ ...prev, [paramName]: value }));
                }}
                className={`w-full px-3 py-2 border border-input rounded-md bg-background text-foreground ${
                  isRequired && !parameters[paramName] && parameters[paramName] !== defaultValue 
                    ? 'border-red-500' 
                    : ''
                }`}
                placeholder={paramType === 'boolean' ? undefined : (defaultValue || `Enter ${paramName}`)}
                required={isRequired}
              />
            )}
            
            {isRequired && !parameters[paramName] && parameters[paramName] !== defaultValue && (
              <p className="text-xs text-red-500">This parameter is required</p>
            )}
          </div>
        );
      });
    }
    
    if (block.type === 'prompt' && block.data?.arguments) {
      return block.data.arguments.map((arg: any) => {
        const isRequired = arg.required !== false;
        
        return (
          <div key={arg.name} className="space-y-2">
            <label className="block text-sm font-medium">
              <span className="flex items-center gap-2">
                {arg.name}
                {isRequired && <span className="text-red-500 text-lg">*</span>}
                <span className="text-xs text-muted-foreground">(string)</span>
              </span>
            </label>
            {arg.description && arg.description !== 'No description' && (
              <p className="text-xs text-muted-foreground">{arg.description}</p>
            )}
            <input
              type="text"
              value={parameters[arg.name] || ''}
              onChange={(e) => setParameters(prev => ({ ...prev, [arg.name]: e.target.value }))}
              className={`w-full px-3 py-2 border border-input rounded-md bg-background text-foreground ${
                isRequired && !parameters[arg.name] 
                  ? 'border-red-500' 
                  : ''
              }`}
              placeholder={`Enter ${arg.name}`}
              required={isRequired}
            />
            {isRequired && !parameters[arg.name] && (
              <p className="text-xs text-red-500">This argument is required</p>
            )}
          </div>
        );
      });
    }
    
    return (
      <div className="text-center text-muted-foreground py-4">
        <p>No parameters to configure</p>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background border border-border rounded-lg p-6 w-full max-w-md max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl">
              {block.type === 'tool' ? '🔧' : block.type === 'prompt' ? '💬' : '📄'}
            </span>
            <h3 className="text-lg font-semibold">
              Configure {block.type === 'tool' ? 'Tool' : block.type === 'prompt' ? 'Prompt' : 'Resource'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted"
          >
            ✕
          </button>
        </div>
        
        <div className="space-y-4">
          <div className="p-4 bg-muted/50 rounded-lg border">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-medium text-sm">{block.name}</span>
              {block.server && (
                <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                  {block.server}
                </span>
              )}
            </div>
            {block.data?.description && (
              <p className="text-sm text-muted-foreground">
                {block.data.description}
              </p>
            )}
          </div>
          
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-foreground">Parameters</h4>
            {getParameterFields()}
          </div>
          
          {/* Test Results Section */}
          <div className="space-y-4 mt-6">
            <h4 className="text-sm font-medium text-foreground">Test Results</h4>
            {testResult ? (
              <div className={`p-4 rounded-lg border ${
                testResult.success 
                  ? 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800' 
                  : 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">
                    {testResult.success ? '✅' : '❌'}
                  </span>
                  <span className={`text-sm font-medium ${
                    testResult.success ? 'text-green-800 dark:text-green-200' : 'text-red-800 dark:text-red-200'
                  }`}>
                    {testResult.success ? 'Test Successful' : 'Test Failed'}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(testResult.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                
                {testResult.error && (
                  <div className="mb-3">
                    <p className="text-sm font-medium text-red-800 dark:text-red-200 mb-1">Error:</p>
                    <p className="text-sm text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/30 p-2 rounded border">
                      {testResult.error}
                    </p>
                  </div>
                )}
                
                {testResult.result && (
                  <div>
                    <p className="text-sm font-medium text-foreground mb-2">Result:</p>
                    <div className="bg-muted/50 p-3 rounded border max-h-40 overflow-y-auto">
                      <pre className="text-xs text-foreground whitespace-pre-wrap break-words">
                        {typeof testResult.result === 'string' 
                          ? testResult.result 
                          : JSON.stringify(testResult.result, null, 2)
                        }
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 rounded-lg border border-muted bg-muted/30">
                <p className="text-sm text-muted-foreground text-center">
                  Click "Test {block.type === 'tool' ? 'Tool' : 'Prompt'}" to test with current parameters
                </p>
              </div>
            )}
          </div>
        </div>
        
        <div className="flex justify-between items-center mt-6">
          <button
            onClick={handleTest}
            disabled={isTesting}
            className="px-4 py-2 text-sm border border-input rounded-md hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            title={`Test ${block.type === 'tool' ? 'tool' : 'prompt'} with current parameters`}
          >
            {isTesting ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
                Testing...
              </>
            ) : (
              <>
                🧪 Test {block.type === 'tool' ? 'Tool' : 'Prompt'}
              </>
            )}
          </button>
          
          <div className="flex space-x-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm border border-input rounded-md hover:bg-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const VMCPMonacoEditor: React.FC<VMCPMonacoEditorProps> = ({
  value,
  onChange,
  height = 240,
  className,
  vmcpConfig,
  editKey,
  editIndex,
  readOnly = false,
  language,
  showSyntaxGuide = true,
  setVmcpConfig
}) => {
  const monacoRef = useRef<any>(null);
  const providersRef = useRef<any[]>([]);
  const atomicBlocksRef = useRef<Map<string, AtomicBlock>>(new Map());
  const decorationsRef = useRef<any[]>([]);
  const isUpdatingAtomicBlockRef = useRef<boolean>(false);
  const decorationUpdateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const positionUpdateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const newlyInsertedBlocksRef = useRef<Set<string>>(new Set());
  const pendingChangesRef = useRef<any[]>([]);
  const isCreatingAtomicBlockRef = useRef<boolean>(false);
  const pendingAtomicBlockRef = useRef<any>(null);
  const [modalState, setModalState] = useState<{
    isOpen: boolean;
    block: AtomicBlock | null;
  }>({ isOpen: false, block: null });

  // Custom theme and language definition
  const languageConfig = useMemo(() => ({
    languageId: "vmcp",
    themeId: "vmcp-theme",
    monarch: {
      defaultToken: "text",
      tokenizer: {
        root: [
          // Environment variables: @env.VAR_NAME
          [/config\.\w+/, "envVariable"],
          // Local variables: @var.variable_name  
          [/param\.\w+/, "localVariable"],
          // Tool calls: @tool.server.tool_name()
          [/tool\.\w+\.\w+\(/, { token: "toolCall", next: "toolargs" }],
          // Prompt calls: @prompt.server.prompt_name()
          [/prompt\.\w+\.\w+\(/, { token: "promptCall", next: "promptargs" }],
          // Resource references: @resource.server.resource_name
          [/resource\.\w+\.\w+[^\s]*/, "resourceRef"],
          // @ symbol for triggering completion
          [/@/, "atSymbol"],
        ],
        toolargs: [
          [/\)/, { token: "toolCall", next: "@pop" }],
          [/config\.\w+/, "envVariable"],
          [/param\.\w+/, "localVariable"],
          [/tool\.\w+\.\w+\(/, { token: "toolCall", next: "toolargs" }],
          [/resource\.\w+\.\w+[^\s]*/, "resourceRef"],
          [/\w+(?=\s*:)/, "paramName"],
          [/:\s*(int|str|bool|float|\[str\]|\[int\]|\[bool\]|\[float\]|dict|list)/, "datatype"],
          [/\w+(?=\s*=)/, "paramName"],
          [/"[^"]*"/, "string"],
          [/'[^']*'/, "string"],
          [/,/, "delimiter"],
          [/=/, "operator"],
          [/\s+/, ""],
        ],
        promptargs: [
          [/\)/, { token: "promptCall", next: "@pop" }],
          [/config\.\w+/, "envVariable"],
          [/param\.\w+/, "localVariable"],
          [/tool\.\w+\.\w+\(/, { token: "toolCall", next: "toolargs" }],
          [/resource\.\w+\.\w+[^\s]*/, "resourceRef"],
          [/\w+(?=\s*:)/, "paramName"],
          [/:\s*(int|str|bool|float|\[str\]|\[int\]|\[bool\]|\[float\]|dict|list)/, "datatype"],
          [/\w+(?=\s*=)/, "paramName"],
          [/"[^"]*"/, "string"],
          [/'[^']*'/, "string"],
          [/,/, "delimiter"],
          [/=/, "operator"],
          [/\s+/, ""],
        ],
      },
    },
    theme: {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "envVariable", foreground: "4EC9B0", fontStyle: "bold" }, // Teal
        { token: "localVariable", foreground: "DCDCAA", fontStyle: "bold" }, // Light yellow
        { token: "toolCall", foreground: "569CD6", fontStyle: "bold" }, // Blue
        { token: "promptCall", foreground: "C586C0", fontStyle: "bold" }, // Purple
        { token: "resourceRef", foreground: "9CDCFE", fontStyle: "bold" }, // Light blue
        { token: "paramName", foreground: "9CDCFE" }, // Light blue
        { token: "datatype", foreground: "6A6A6A", fontStyle: "italic" }, // Muted gray for datatypes
        { token: "string", foreground: "CE9178" }, // Orange
        { token: "operator", foreground: "D4D4D4" }, // Light gray
        { token: "delimiter", foreground: "808080" }, // Gray
        { token: "atSymbol", foreground: "FF6B6B", fontStyle: "bold" }, // Red
      ],
      colors: {
        "editor.background": "#1E1E1E",
        "editor.foreground": "#D4D4D4",
        "editorCursor.foreground": "#AEAFAD",
        "editor.lineHighlightBackground": "#2D2D30",
        "editorLineNumber.foreground": "#858585",
        "editor.selectionBackground": "#264F78",
        "editor.inactiveSelectionBackground": "#3A3D41"
      },
    },
  }), []);

  // Generate completion data based on vmcpConfig and edit context
  const completionData = useMemo(() => {
    console.log(`🔄 [VMCPEditor] Generating completion data...`, { 
      hasConfig: !!vmcpConfig, 
      editKey, 
      editIndex 
    });

    if (!vmcpConfig) {
      return {
        envCompletions: [],
        varCompletions: [],
        toolCompletions: [],
        promptCompletions: [],
        resourceCompletions: []
      };
    }

    // Ensure vmcpConfig has the required structure
    if (!vmcpConfig.vmcp_config) {
      return {
        envCompletions: [],
        varCompletions: [],
        toolCompletions: [],
        promptCompletions: [],
        resourceCompletions: []
      };
    }

    // 1. Environment Variables - @env.VAR_NAME
    const envCompletions: CompletionItem[] = (vmcpConfig.environment_variables || [])
      .map(env => ({
        completion: `config.${env.name}`,
        label: env.name,
        description: env.description || `Environment variable: ${env.name}`,
        kind: 'env'
      }));

    // 2. Local Variables - @var.variable_name (context-dependent)
    let contextVariables: Array<{ name: string; description: string; required: boolean }> = [];
    
    if (editKey === "system_prompt") {
      contextVariables = vmcpConfig.system_prompt?.variables || [];
    } else if (editKey === "custom_prompt" && editIndex !== null && editIndex !== undefined) {
      const prompt = vmcpConfig.custom_prompts?.[editIndex];
      contextVariables = prompt?.variables || [];
    } else if (editKey === "custom_tool" && editIndex !== null && editIndex !== undefined) {
      const tool = vmcpConfig.custom_tools?.[editIndex];
      contextVariables = tool?.variables || [];
    }

    const varCompletions: CompletionItem[] = contextVariables.map(variable => ({
      completion: `param.${variable.name}`,
      label: variable.name,
      description: variable.description || `Variable: ${variable.name}`,
      kind: 'var'
    }));

    // 3. Tools - @tool.server.tool_name()
    const toolCompletions: CompletionItem[] = [];
    
    // Add custom tools
    if (vmcpConfig.custom_tools) {
      vmcpConfig.custom_tools.forEach(tool => {
        toolCompletions.push({
          completion: `tool.vmcp.${tool.name}`,
          label: `vmcp.${tool.name}`,
          description: tool.description || `Custom tool: ${tool.name}`,
          kind: 'tool',
          server: 'custom',
          serverId: 'custom',
          toolData: {
            label: `vmcp.${tool.name}`,
            name: tool.name,
            server: 'custom',
            serverId: 'custom',
            description: tool.description,
            inputSchema: { properties: {}, required: [] } // Custom tools don't have input schema in this structure
          }
        });
      });
    }

    // Add MCP server tools
    if (vmcpConfig.vmcp_config?.selected_tools) {
      Object.entries(vmcpConfig.vmcp_config.selected_tools).forEach(([serverId, toolNames]) => {
        if (Array.isArray(toolNames)) {
          // Find server configuration by server_id (not name)
          const serverConfig = vmcpConfig.vmcp_config.selected_servers?.find(
            s => s.server_id === serverId
          );
          
          console.log(`🔍 [VMCPEditor] Processing server: ${serverId}`, {
            serverConfig: serverConfig,
            toolDetails: serverConfig?.tool_details,
            toolNames: toolNames
          });
          
          // Get available tool details from the server config
          const availableToolDetails = (serverConfig as any)?.tool_details || [];
          
          // Only process tools that exist in both selected_tools AND tool_details
          const validToolNames = toolNames.filter(toolName => 
            availableToolDetails.some((tool: any) => tool.name === toolName)
          );
          
          console.log(`🔍 [VMCPEditor] Valid tools for server ${serverId}:`, {
            selected: toolNames,
            available: availableToolDetails.map((t: any) => t.name),
            valid: validToolNames
          });
          
          validToolNames.forEach(toolName => {
            // Find the tool details from the available tools
            const toolDetail = availableToolDetails.find(
              (t: any) => t.name === toolName
            );
            
            if (toolDetail) {
              console.log(`🔍 [VMCPEditor] Tool: ${toolName}`, {
                toolDetail: toolDetail,
                hasDescription: !!toolDetail?.description,
                hasInputSchema: !!toolDetail?.inputSchema,
                serverConfigKeys: Object.keys(serverConfig || {}),
                toolDetailsArray: availableToolDetails.length
              });
              
              const serverName = serverConfig?.name || serverId;
              toolCompletions.push({
                completion: `tool.${serverName}.${toolName}`,
                label: `${serverName}.${toolName}`,
                description: toolDetail.description || `Tool from ${serverName} server`,
                kind: 'tool',
                server: serverName,
                serverId: serverId,
                toolData: {
                  label: `${serverName}.${toolName}`,
                  name: toolName,
                  server: serverName,
                  serverId: serverId,
                  description: toolDetail.description,
                  inputSchema: toolDetail.inputSchema || { properties: {}, required: [] }
                }
              });
            } else {
              console.warn(`⚠️ [VMCPEditor] Tool ${toolName} not found in available tool details`);
            }
          });
          
          // Log any tools that were selected but not available
          const missingTools = toolNames.filter(toolName => 
            !availableToolDetails.some((tool: any) => tool.name === toolName)
          );
          if (missingTools.length > 0) {
            console.warn(`⚠️ [VMCPEditor] Selected tools not found in tool_details:`, missingTools);
          }
        }
      });
    }

    // 4. Prompts - @prompt.server.prompt_name()
    const promptCompletions: CompletionItem[] = [];
    
    // Add custom prompts
    if (vmcpConfig.custom_prompts) {
      vmcpConfig.custom_prompts.forEach(prompt => {
        promptCompletions.push({
          completion: `prompt.vmcp.${prompt.name}`,
          label: `vmcp.${prompt.name}`,
          description: prompt.description || `Custom prompt: ${prompt.name}`,
          kind: 'prompt',
          server: 'custom',
          serverId: 'custom',
          promptData: {
            label: `vmcp.${prompt.name}`,
            name: prompt.name,
            server: 'custom',
            serverId: 'custom',
            description: prompt.description,
            arguments: prompt.variables?.map(v => ({
              name: v.name,
              description: v.description,
              required: v.required
            })) || []
          }
        });
      });
    }

    // Add MCP server prompts
    if (vmcpConfig.vmcp_config?.selected_prompts) {
      Object.entries(vmcpConfig.vmcp_config.selected_prompts).forEach(([serverId, promptNames]) => {
        if (Array.isArray(promptNames)) {
          // Find server configuration by server_id (not name)
          const serverConfig = vmcpConfig.vmcp_config.selected_servers?.find(
            s => s.server_id === serverId
          );
          
          console.log(`🔍 [VMCPEditor] Processing prompts for server: ${serverId}`, {
            serverConfig: serverConfig,
            promptDetails: serverConfig?.prompt_details,
            promptNames: promptNames
          });
          
          // Get available prompt details from the server config
          const availablePromptDetails = (serverConfig as any)?.prompt_details || [];
          
          // Only process prompts that exist in both selected_prompts AND prompt_details
          const validPromptNames = promptNames.filter(promptName => 
            availablePromptDetails.some((prompt: any) => prompt.name === promptName)
          );
          
          console.log(`🔍 [VMCPEditor] Valid prompts for server ${serverId}:`, {
            selected: promptNames,
            available: availablePromptDetails.map((p: any) => p.name),
            valid: validPromptNames
          });
          
          validPromptNames.forEach(promptName => {
            // Find the prompt details from the available prompts
            const promptDetail = availablePromptDetails.find(
              (p: any) => p.name === promptName
            );
            
            if (promptDetail) {
              console.log(`🔍 [VMCPEditor] Prompt: ${promptName}`, {
                promptDetail: promptDetail,
                hasDescription: !!promptDetail?.description,
                hasArguments: !!promptDetail?.arguments,
                serverConfigKeys: Object.keys(serverConfig || {}),
                promptDetailsArray: availablePromptDetails.length
              });
              
              const serverName = serverConfig?.name || serverId;
              promptCompletions.push({
                completion: `prompt.${serverName}.${promptName}`,
                label: `${serverName}.${promptName}`,
                description: promptDetail.description || `Prompt from ${serverName} server`,
                kind: 'prompt',
                server: serverName,
                serverId: serverId,
                promptData: {
                  label: `${serverName}.${promptName}`,
                  name: promptName,
                  server: serverName,
                  serverId: serverId,
                  description: promptDetail.description,
                  arguments: promptDetail.arguments?.map((v: any) => ({
                    name: v.name,
                    description: v.description,
                    required: v.required
                  })) || []
                }
              });
            } else {
              console.warn(`⚠️ [VMCPEditor] Prompt ${promptName} not found in available prompt details`);
            }
          });
          
          // Log any prompts that were selected but not available
          const missingPrompts = promptNames.filter(promptName => 
            !availablePromptDetails.some((prompt: any) => prompt.name === promptName)
          );
          if (missingPrompts.length > 0) {
            console.warn(`⚠️ [VMCPEditor] Selected prompts not found in prompt_details:`, missingPrompts);
          }
        }
      });
    }

    // 5. Resources - @resource.server.resource_name
    const resourceCompletions: CompletionItem[] = [];
    
    // Add custom resources
    if (vmcpConfig.custom_resources) {
      vmcpConfig.custom_resources.forEach(resource => {
        // Handle both string and object formats
        const resourceName = typeof resource === 'string' 
          ? resource 
          : resource.resource_name || resource.filename || resource.original_filename || 'unknown';
        
        const resourceDescription = typeof resource === 'object' && resource.content_type
          ? `Custom resource: ${resourceName} (${resource.content_type})`
          : `Custom resource: ${resourceName}`;
        
        resourceCompletions.push({
          completion: `resource.vmcp.${resourceName}`,
          label: `vmcp.${resourceName}`,
          description: resourceDescription,
          kind: 'resource',
          server: 'custom'
        });
      });
    }

    // Add MCP server resources
    if (vmcpConfig.vmcp_config?.selected_resources) {
      Object.entries(vmcpConfig.vmcp_config.selected_resources).forEach(([serverId, resourceNames]) => {
        if (Array.isArray(resourceNames)) {
          // Find server configuration by server_id (not name)
          const serverConfig = vmcpConfig.vmcp_config.selected_servers?.find(
            s => s.server_id === serverId
          );
          const serverName = serverConfig?.name || serverId;
          
          resourceNames.forEach(resourceName => {
            resourceCompletions.push({
              completion: `resource.${serverName}.${resourceName}`,
              label: `${serverName}.${resourceName}`,
              description: `Resource from ${serverName} server`,
              kind: 'resource',
              server: serverName
            });
          });
        }
      });
    }

    console.log(`✅ [VMCPEditor] Completion data generated:`, {
      env: envCompletions.length,
      var: varCompletions.length, 
      tool: toolCompletions.length,
      prompt: promptCompletions.length,
      resource: resourceCompletions.length
    });

    return {
      envCompletions,
      varCompletions,
      toolCompletions,
      promptCompletions,
      resourceCompletions
    };
  }, [vmcpConfig, editKey, editIndex]);

  // Helper functions for atomic block management
  const generateBlockId = useCallback(() => {
    return `block_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  // Function to extract default values from tool/prompt data
  const extractDefaultValues = useCallback((data: any, type: 'tool' | 'prompt'): Record<string, any> => {
    const defaults: Record<string, any> = {};
    
    console.log(`🔍 [VMCPEditor] Extracting defaults for ${type}:`, data);
    
    if (type === 'tool' && data?.inputSchema?.properties) {
      const properties = data.inputSchema.properties;
      console.log(`🔍 [VMCPEditor] Tool properties:`, properties);
      
      Object.entries(properties).forEach(([paramName, schema]: [string, any]) => {
        console.log(`🔍 [VMCPEditor] Parameter ${paramName}:`, schema);
        if (schema.default !== undefined) {
          defaults[paramName] = schema.default;
          console.log(`✅ [VMCPEditor] Set default for ${paramName}:`, schema.default);
        }
      });
    } else if (type === 'prompt' && data?.arguments) {
      console.log(`🔍 [VMCPEditor] Prompt arguments:`, data.arguments);
      data.arguments.forEach((arg: any) => {
        if (arg.default !== undefined) {
          defaults[arg.name] = arg.default;
          console.log(`✅ [VMCPEditor] Set default for ${arg.name}:`, arg.default);
        }
      });
    }
    
    console.log(`🎯 [VMCPEditor] Extracted defaults:`, defaults);
    return defaults;
  }, []);

  const createAtomicBlock = useCallback((
    startLine: number,
    startColumn: number,
    endLine: number,
    endColumn: number,
    type: AtomicBlock['type'],
    server: string | undefined,
    name: string,
    text: string,
    data: any,
    parameters: Record<string, any> = {}
  ): AtomicBlock => {
    return {
      id: generateBlockId(),
      startLine,
      startColumn,
      endLine,
      endColumn,
      type,
      server,
      serverId: data?.serverId || 'custom',
      name,
      text,
      data,
      parameters
    };
  }, [generateBlockId]);

  const updateAtomicBlockDecorations = useCallback(() => {
    const { editor } = monacoRef.current || {};
    if (!editor) return;

    // Clear any pending decoration update
    if (decorationUpdateTimeoutRef.current) {
      clearTimeout(decorationUpdateTimeoutRef.current);
    }

    // Debounce decoration updates to prevent recursive calls
    decorationUpdateTimeoutRef.current = setTimeout(() => {
      // Clear existing decorations
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);

      // Create decorations for all atomic blocks
      const decorations = Array.from(atomicBlocksRef.current.values()).map(block => ({
        range: new (window as any).monaco.Range(
          block.startLine,
          block.startColumn,
          block.endLine,
          block.endColumn
        ),
        options: {
          className: 'atomic-block-highlight',
          hoverMessage: {
            value: `**Atomic Block**: ${block.type === 'tool' ? 'Tool' : 'Prompt'} - ${block.name}\nClick to configure parameters`
          },
          isWholeLine: false,
          stickiness: 1 // Track with text
        }
      }));

      // Apply decorations
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, decorations);
    }, 10); // Small delay to prevent recursion
  }, []);

  const updateAtomicBlockPositions = useCallback((change: any) => {
    // Add change to pending changes instead of replacing
    pendingChangesRef.current.push(change);
    
    // Clear any pending position update
    if (positionUpdateTimeoutRef.current) {
      clearTimeout(positionUpdateTimeoutRef.current);
    }

    // Process all pending changes after a short delay
    positionUpdateTimeoutRef.current = setTimeout(() => {
      const changes = [...pendingChangesRef.current];
      pendingChangesRef.current = []; // Clear pending changes
      
      console.log(`🔄 [VMCPEditor] Processing ${changes.length} pending changes`);
      
      // Process each change in sequence
      changes.forEach((change, index) => {
        const { text, range } = change;
        const changeStartLine = range.startLineNumber;
        const changeStartColumn = range.startColumn;
        const changeEndLine = range.endLineNumber;
        const changeEndColumn = range.endColumn;
      
        // Calculate the line and column delta
        const textLines = text ? text.split('\n') : [''];
        const lineDelta = textLines.length - (changeEndLine - changeStartLine + 1);
        
        // Fix column delta calculation for newlines and other cases
        let columnDelta = 0;
        if (textLines.length === 1) {
          // Single line change - calculate normal column delta
          columnDelta = textLines[0].length - (changeEndColumn - changeStartColumn);
        } else if (textLines.length > 1) {
          // Multi-line change - only the last line affects column position
          columnDelta = textLines[textLines.length - 1].length - (changeEndColumn - changeStartColumn);
        }
        
        console.log(`🔄 [VMCPEditor] Processing change ${index + 1}/${changes.length}:`, {
          changeStartLine,
          changeStartColumn,
          changeEndLine,
          changeEndColumn,
          lineDelta,
          columnDelta,
          text: text?.substring(0, 50) + (text?.length > 50 ? '...' : ''),
          textLines: textLines,
          isNewline: text === '\n',
          isMultiLine: textLines.length > 1
        });
        
        // Update positions of atomic blocks that come after this change
        const updatedBlocks = new Map<string, AtomicBlock>();
        
        for (const [id, block] of atomicBlocksRef.current.entries()) {
          let updatedBlock = { ...block };
          
          // Skip newly inserted blocks - they shouldn't be affected by position updates
          if (newlyInsertedBlocksRef.current.has(block.id)) {
            console.log(`⏭️ [VMCPEditor] Skipping newly inserted block:`, block.id);
            updatedBlocks.set(id, updatedBlock);
            continue;
          }
          
          // Check if the block is being modified (overlaps with the change)
          const blockOverlaps = (
            (block.startLine < changeEndLine || (block.startLine === changeEndLine && block.startColumn < changeEndColumn)) &&
            (block.endLine > changeStartLine || (block.endLine === changeStartLine && block.endColumn > changeStartColumn))
          );
          
          if (blockOverlaps) {
            // Block is being modified - remove it as it's no longer valid
            // But skip removal if we're updating via modal (to prevent wrong tool data)
            if (isUpdatingAtomicBlockRef.current) {
              console.log(`⏭️ [VMCPEditor] Skipping overlap removal during modal update:`, block.id);
              updatedBlocks.set(id, updatedBlock);
              continue;
            }
            console.log(`🗑️ [VMCPEditor] Removing modified atomic block:`, block.id);
            continue;
          }
          
          // Check if the block is after the change point
          const blockIsAfter = block.startLine > changeStartLine;
          const blockIsOnSameLineAfter = block.startLine === changeStartLine && block.startColumn >= changeStartColumn;
          
          console.log(`🔍 [VMCPEditor] Processing block ${block.id}:`, {
            blockStartLine: block.startLine,
            blockStartColumn: block.startColumn,
            blockEndLine: block.endLine,
            blockEndColumn: block.endColumn,
            changeStartLine,
            changeStartColumn,
            blockIsAfter,
            blockIsOnSameLineAfter,
            lineDelta,
            columnDelta
          });
          
          if (blockIsAfter) {
            // Block is after the change - only update line numbers
            const oldStartLine = updatedBlock.startLine;
            const oldEndLine = updatedBlock.endLine;
            updatedBlock.startLine += lineDelta;
            updatedBlock.endLine += lineDelta;
            
            console.log(`📝 [VMCPEditor] Updated block ${block.id} - moved to new line:`, {
              oldStartLine,
              oldEndLine,
              newStartLine: updatedBlock.startLine,
              newEndLine: updatedBlock.endLine,
              lineDelta
            });
          } else if (blockIsOnSameLineAfter) {
            // Block is on the same line but after the insertion point - update columns
            const oldStartColumn = updatedBlock.startColumn;
            const oldEndColumn = updatedBlock.endColumn;
            updatedBlock.startColumn += columnDelta;
            updatedBlock.endColumn += columnDelta;
            
            console.log(`📝 [VMCPEditor] Updated block ${block.id} - shifted columns:`, {
              oldStartColumn,
              oldEndColumn,
              newStartColumn: updatedBlock.startColumn,
              newEndColumn: updatedBlock.endColumn,
              columnDelta
            });
          } else {
            console.log(`⏭️ [VMCPEditor] Block ${block.id} not affected by change`);
          }
          
          updatedBlocks.set(id, updatedBlock);
        }
        
        // Update the atomic blocks map
        atomicBlocksRef.current = updatedBlocks;
      });
      
      // Update decorations with new positions
      updateAtomicBlockDecorations();
      
      // Save the updated atomic blocks to VMCP configuration
      saveAtomicBlocks();
    }, 50); // Reduced debounce time to 50ms for faster processing
  }, [updateAtomicBlockDecorations]);

  const registerAtomicBlock = useCallback((block: AtomicBlock) => {
    atomicBlocksRef.current.set(block.id, block);
    updateAtomicBlockDecorations();
  }, [updateAtomicBlockDecorations]);

  const findAtomicBlockAtPosition = useCallback((line: number, column: number): AtomicBlock | null => {
    for (const block of atomicBlocksRef.current.values()) {
      if (line >= block.startLine && line <= block.endLine) {
        if (line === block.startLine && column < block.startColumn) continue;
        if (line === block.endLine && column > block.endColumn) continue;
        return block;
      }
    }
    return null;
  }, []);

  const findAtomicBlocksInRange = useCallback((startLine: number, startColumn: number, endLine: number, endColumn: number): AtomicBlock[] => {
    const blocks: AtomicBlock[] = [];
    for (const block of atomicBlocksRef.current.values()) {
      // Check if the deletion range overlaps with the atomic block
      const deletionOverlapsBlock = (
        (startLine < block.endLine || (startLine === block.endLine && startColumn <= block.endColumn)) &&
        (endLine > block.startLine || (endLine === block.startLine && endColumn >= block.startColumn))
      );
      
      if (deletionOverlapsBlock) {
        blocks.push(block);
      }
    }
    return blocks;
  }, []);

  // Function to save atomic blocks to the current prompt/tool
  const saveAtomicBlocks = useCallback(() => {
    if (!vmcpConfig || !editKey || editIndex === undefined || editIndex === null || !setVmcpConfig) return;

    const atomicBlocksArray = Array.from(atomicBlocksRef.current.values()).map(block => ({
      id: block.id,
      startLine: block.startLine,
      startColumn: block.startColumn,
      endLine: block.endLine,
      endColumn: block.endColumn,
      type: block.type,
      server: block.server || '',
      serverId: block.serverId || '',
      name: block.name,
      text: block.text,
      data: block.data,
      parameters: block.parameters || {}
    }));

    console.log(`💾 [VMCPEditor] Saving atomic blocks for ${editKey}[${editIndex}]:`, atomicBlocksArray);

    // Update the atomic_blocks field in the appropriate array using setVmcpConfig
    setVmcpConfig(prev => {
      const newConfig = { ...prev };
      
      if (editKey === 'custom_prompt' && newConfig.custom_prompts[editIndex]) {
        newConfig.custom_prompts[editIndex] = {
          ...newConfig.custom_prompts[editIndex],
          atomic_blocks: atomicBlocksArray
        };
      } else if (editKey === 'custom_tool' && newConfig.custom_tools[editIndex]) {
        newConfig.custom_tools[editIndex] = {
          ...newConfig.custom_tools[editIndex],
          atomic_blocks: atomicBlocksArray
        };
      }
      
      return newConfig;
    });
  }, [vmcpConfig, editKey, editIndex, setVmcpConfig]);

  // Function to restore atomic blocks from saved data
  const restoreAtomicBlocks = useCallback(() => {
    if (!vmcpConfig || !editKey || editIndex === undefined || editIndex === null) return;

    let savedAtomicBlocks: any[] = [];
    
    if (editKey === 'custom_prompt' && vmcpConfig.custom_prompts[editIndex]?.atomic_blocks) {
      savedAtomicBlocks = vmcpConfig.custom_prompts[editIndex].atomic_blocks || [];
    } else if (editKey === 'custom_tool' && vmcpConfig.custom_tools[editIndex]?.atomic_blocks) {
      savedAtomicBlocks = vmcpConfig.custom_tools[editIndex].atomic_blocks || [];
    }

    console.log(`🔄 [VMCPEditor] Restoring atomic blocks for ${editKey}[${editIndex}]:`, savedAtomicBlocks);

    // Clear existing atomic blocks
    atomicBlocksRef.current.clear();

    // Restore atomic blocks from saved data
    const { editor } = monacoRef.current || {};
    if (editor) {
      const model = editor.getModel();
      if (model) {
        savedAtomicBlocks.forEach(blockData => {
          // Validate that the saved positions are still valid
          const maxLine = model.getLineCount();
          const maxColumn = model.getLineContent(blockData.startLine).length + 1;
          
          if (blockData.startLine > maxLine || 
              blockData.endLine > maxLine || 
              blockData.startColumn > maxColumn || 
              blockData.endColumn > maxColumn) {
            console.warn(`⚠️ [VMCPEditor] Skipping invalid atomic block position:`, {
              id: blockData.id,
              startLine: blockData.startLine,
              endLine: blockData.endLine,
              maxLine,
              maxColumn
            });
            return;
          }
          
          // Check if the text at the saved position matches the saved text
          const currentText = model.getValueInRange({
            startLineNumber: blockData.startLine,
            startColumn: blockData.startColumn,
            endLineNumber: blockData.endLine,
            endColumn: blockData.endColumn
          });
          
          if (currentText !== blockData.text) {
            console.warn(`⚠️ [VMCPEditor] Text mismatch for atomic block:`, {
              id: blockData.id,
              savedText: blockData.text,
              currentText: currentText.substring(0, 50) + (currentText.length > 50 ? '...' : ''),
              position: `${blockData.startLine}:${blockData.startColumn}-${blockData.endLine}:${blockData.endColumn}`
            });
            return;
          }
          
          const atomicBlock: AtomicBlock = {
            id: blockData.id,
            startLine: blockData.startLine,
            startColumn: blockData.startColumn,
            endLine: blockData.endLine,
            endColumn: blockData.endColumn,
            type: blockData.type,
            server: blockData.server,
            serverId: blockData.serverId,
            name: blockData.name,
            text: blockData.text,
            data: blockData.data,
            parameters: blockData.parameters || {}
          };
          
          atomicBlocksRef.current.set(atomicBlock.id, atomicBlock);
          console.log(`✅ [VMCPEditor] Restored atomic block:`, {
            id: atomicBlock.id,
            name: atomicBlock.name,
            position: `${atomicBlock.startLine}:${atomicBlock.startColumn}-${atomicBlock.endLine}:${atomicBlock.endColumn}`
          });
        });
      }
    } else {
      // Fallback: restore without validation if editor is not available
      savedAtomicBlocks.forEach(blockData => {
        const atomicBlock: AtomicBlock = {
          id: blockData.id,
          startLine: blockData.startLine,
          startColumn: blockData.startColumn,
          endLine: blockData.endLine,
          endColumn: blockData.endColumn,
          type: blockData.type,
          server: blockData.server,
          serverId: blockData.serverId,
          name: blockData.name,
          text: blockData.text,
          data: blockData.data,
          parameters: blockData.parameters || {}
        };
        
        atomicBlocksRef.current.set(atomicBlock.id, atomicBlock);
      });
    }

    // Update decorations to show the restored blocks
    updateAtomicBlockDecorations();
  }, [vmcpConfig, editKey, editIndex, updateAtomicBlockDecorations]);

  const handleAtomicBlockClick = useCallback((block: AtomicBlock) => {
    console.log(`🚨 [VMCPEditor] MODAL OPENING - handleAtomicBlockClick called:`, {
      blockId: block.id,
      blockType: block.type,
      blockName: block.name,
      blockServer: block.server,
      position: `${block.startLine}:${block.startColumn}-${block.endLine}:${block.endColumn}`,
      stackTrace: new Error().stack
    });
    setModalState({ isOpen: true, block });
  }, []);

  // Function to prevent cursor from entering atomic block parameters
  const preventAtomicBlockEditing = useCallback((editor: any) => {
    editor.onDidChangeCursorPosition((e: any) => {
      const position = e.position;
      const block = findAtomicBlockAtPosition(position.lineNumber, position.column);
      
      if (block) {
        // Check if cursor is trying to enter the parameter area (inside parentheses)
        const text = editor.getModel()?.getLineContent(position.lineNumber) || '';
        const blockText = text.substring(block.startColumn - 1, block.endColumn);
        
        // If cursor is inside parentheses of an atomic block, move it to the end
        if (blockText.includes('(') && blockText.includes(')')) {
          const openParenIndex = blockText.indexOf('(');
          const closeParenIndex = blockText.lastIndexOf(')');
          const relativePos = position.column - block.startColumn;
          
          // Check if cursor is inside the parentheses (but not at the very end)
          if (relativePos > openParenIndex && relativePos < closeParenIndex) {
            console.log(`🚫 [VMCPEditor] Cursor inside atomic block, moving to end`);
            
            // Move cursor to the end of the atomic block
            editor.setPosition({
              lineNumber: block.endLine,
              column: block.endColumn
            });
            
            // Only show modal if this is a deliberate click (not during selection)
            // Use a small delay to check if cursor position is stable
            // cursorChangeTimeout = setTimeout(() => {
            //   const currentSelection = editor.getSelection();
            //   const hasSelection = currentSelection && !currentSelection.isEmpty();
            //   
            //   // Only open modal if there's no active selection and cursor is stable
            //   if (!hasSelection) {
            //     console.log(`🚨 [VMCPEditor] MODAL OPENING - Called from cursor position handler (onDidChangeCursorPosition)`);
            //     handleAtomicBlockClick(block);
            //   }
            // }, 100);
          }
        }
      }
    });

    // Prevent direct editing of atomic blocks
    editor.onDidChangeModelContent((e: any) => {
      if (e.changes.length > 0) {
        for (const change of e.changes) {
          // Check if the change is within an atomic block
          const affectedBlocks = findAtomicBlocksInRange(
            change.range.startLineNumber,
            change.range.startColumn,
            change.range.endLineNumber,
            change.range.endColumn
          );
          
          // If change is strictly within an atomic block, prevent it
          if (affectedBlocks.length > 0 && change.text !== '') {
            const block = affectedBlocks[0];
            
            console.log(`🔍 [VMCPEditor] Change strictly within atomic block, preventing:`, {
              blockId: block.id,
              changeRange: `${change.range.startLineNumber}:${change.range.startColumn}-${change.range.endLineNumber}:${change.range.endColumn}`,
              blockRange: `${block.startLine}:${block.startColumn}-${block.endLine}:${block.endColumn}`,
              changeText: change.text?.substring(0, 20) + (change.text?.length > 20 ? '...' : '')
            });
            
            // Revert the change
            const model = editor.getModel();
            if (model) {
              model.pushEditOperations([], [{
                range: change.range,
                text: change.rangeLength > 0 ? model.getValueInRange(change.range) : '',
                forceMoveMarkers: true
              }], () => null);
              
              // Show modal instead
              console.log(`🚨 [VMCPEditor] MODAL OPENING - Called from content change handler (onDidChangeModelContent)`);
              handleAtomicBlockClick(block);
            }
          }
        }
      }
    });
  }, [findAtomicBlockAtPosition, findAtomicBlocksInRange, handleAtomicBlockClick]);

  // Build tool snippet with actual parameter values
  const buildToolSnippetWithParams = useCallback((toolData: any, parameters: Record<string, any>): string => {
    if (!toolData?.inputSchema?.properties) {
      return `${toolData.label}()`;
    }
    
    const properties = toolData.inputSchema.properties;
    const paramNames = Object.keys(properties);
    
    if (paramNames.length === 0) {
      return `${toolData.label}()`;
    }
    
    const paramsSnippet = paramNames
      .map(paramName => {
        const value = parameters[paramName];
        const schema = properties[paramName] || {};
        const isString = schema.type === "string" || !schema.type;
        const isArray = schema.type === "array";
        const datatype = getDatatypeString(schema);
        
        // For optional parameters, show them as blank if no value provided
        if (value === undefined || value === null || value === '') {
          if (isString) {
            return `${paramName}: ${datatype} = ""`;
          } else if (isArray) {
            return `${paramName}: ${datatype} = []`;
          }
          return `${paramName}: ${datatype} = null`;
        }
        
        if (isString) {
          return `${paramName}: ${datatype} = "${value}"`;
        } else if (isArray) {
          // Format array values properly
          const arrayValue = Array.isArray(value) ? JSON.stringify(value) : '[]';
          return `${paramName}: ${datatype} = ${arrayValue}`;
        }
        return `${paramName}: ${datatype} = ${value}`;
      })
      .join(", ");
      
    return `${toolData.label}(${paramsSnippet})`;
  }, []);

  // Build prompt snippet with actual parameter values
  const buildPromptSnippetWithParams = useCallback((promptData: any, parameters: Record<string, any>): string => {
    if (!promptData?.arguments) {
      return `${promptData.label}()`;
    }
    
    const args = promptData.arguments;
    const paramNames = args.map((arg: any) => arg.name);
    
    if (paramNames.length === 0) {
      return `${promptData.label}()`;
    }
    
    const paramsSnippet = args
      .map((arg: any) => {
        const paramName = arg.name;
        const value = parameters[paramName];
        const datatype = 'str'; // Prompts typically use string parameters
        
        // For optional parameters, show them as blank if no value provided
        if (value === undefined || value === null || value === '') {
          return `${paramName}: ${datatype} = ""`;
        }
        return `${paramName}: ${datatype} = "${value}"`;
      })
      .join(", ");
      
    return `${promptData.label}(${paramsSnippet})`;
  }, []);

  const handleModalSave = useCallback((parameters: Record<string, any>) => {
    if (!modalState.block) return;

    const { editor } = monacoRef.current || {};
    if (!editor) return;

    const model = editor.getModel();
    if (!model) return;

    const oldBlock = modalState.block;
    
    // Set flag to prevent overlap removal during modal update
    isUpdatingAtomicBlockRef.current = true;
    
    // Rebuild the text with new parameters
    let newText = '';
    if (oldBlock.type === 'tool') {
      newText = buildToolSnippetWithParams(oldBlock.data, parameters);
    } else if (oldBlock.type === 'prompt') {
      newText = buildPromptSnippetWithParams(oldBlock.data, parameters);
    } else {
      newText = oldBlock.text;
    }

    // Calculate the change in text length
    const oldLength = oldBlock.endColumn - oldBlock.startColumn;
    const newLength = newText.length;
    const lengthDelta = newLength - oldLength;

    // Update the atomic block with new text and parameters
    const updatedBlock = { 
      ...oldBlock, 
      text: newText,
      parameters,
      endColumn: oldBlock.startColumn + newLength
    };
    
    console.log(`🔄 [VMCPEditor] Updating atomic block:`, {
      id: oldBlock.id,
      oldText: oldBlock.text,
      newText: newText,
      oldLength: oldLength,
      newLength: newLength,
      lengthDelta: lengthDelta
    });

    // Replace the text in the editor
    const range = new (window as any).monaco.Range(
      oldBlock.startLine,
      oldBlock.startColumn,
      oldBlock.endLine,
      oldBlock.endColumn
    );
    
    model.pushEditOperations([], [{
      range,
      text: newText,
      forceMoveMarkers: true
    }], () => null);

    // Update the atomic block in our tracking
    atomicBlocksRef.current.set(updatedBlock.id, updatedBlock);

    // Update positions of all following atomic blocks
    if (lengthDelta !== 0) {
      // Manually update positions of blocks that come after this one
      const updatedBlocks = new Map(atomicBlocksRef.current);
      
      for (const [id, block] of updatedBlocks.entries()) {
        // Skip the block we just updated
        if (block.id === updatedBlock.id) {
          continue;
        }
        
        // Check if the block is after the updated block
        const blockIsAfter = (
          block.startLine > oldBlock.endLine || 
          (block.startLine === oldBlock.endLine && block.startColumn >= oldBlock.endColumn)
        );
        
        if (blockIsAfter) {
          // Block is after the updated block - adjust its position
          const updatedFollowingBlock = { ...block };
          
          // If the change was on the same line, adjust column
          if (block.startLine === oldBlock.endLine) {
            updatedFollowingBlock.startColumn += lengthDelta;
            updatedFollowingBlock.endColumn += lengthDelta;
          }
          
          updatedBlocks.set(id, updatedFollowingBlock);
          console.log(`📍 [VMCPEditor] Updated position for following block:`, {
            id: block.id,
            oldStart: block.startColumn,
            newStart: updatedFollowingBlock.startColumn,
            delta: lengthDelta
          });
        }
      }
      
      // Update the atomic blocks map
      atomicBlocksRef.current = updatedBlocks;
    }

    // Update decorations and save
    updateAtomicBlockDecorations();
    saveAtomicBlocks();

    // Reset flag after modal update is complete (with delay to allow position updates to complete)
    setTimeout(() => {
      isUpdatingAtomicBlockRef.current = false;
      console.log(`🔄 [VMCPEditor] Reset modal update flag`);
    }, 200);

    // Close modal
    setModalState({ isOpen: false, block: null });

    console.log(`✅ [VMCPEditor] Atomic block updated:`, updatedBlock);
  }, [modalState.block, buildToolSnippetWithParams, buildPromptSnippetWithParams, updateAtomicBlockPositions, updateAtomicBlockDecorations, saveAtomicBlocks]);


  // Dispose old providers and register new ones
  const registerProviders = useCallback((editor: any, monaco: any) => {
    // Dispose existing providers
    providersRef.current.forEach(provider => {
      try {
        provider?.dispose?.();
      } catch (e) {
        console.warn('Failed to dispose provider:', e);
      }
    });
    providersRef.current = [];

    // Track completion insertions to create atomic blocks
    let isDeletingAtomicBlock = false;
    
    // Listen for content changes and handle atomic blocks
    editor.onDidChangeModelContent((e: any) => {
      if (e.changes.length > 0) {
        for (const change of e.changes) {
          // Handle new atomic block creation
          if (pendingAtomicBlockRef.current && change.text && change.text.includes('(') && change.text.includes(')') && !isCreatingAtomicBlockRef.current) {
            // This looks like a tool/prompt insertion
            const startLine = change.range.startLineNumber;
            const startColumn = change.range.startColumn;
            const endLine = change.range.endLineNumber;
            const endColumn = change.range.startColumn + change.text.length;
            
            // Prevent duplicate creation
            isCreatingAtomicBlockRef.current = true;
            
            // Clear the pending block immediately to prevent duplicate processing
            const currentPendingBlock = pendingAtomicBlockRef.current;
            pendingAtomicBlockRef.current = null;
            
            // Use a small delay to ensure the text is fully inserted
            setTimeout(() => {
              const blockType = currentPendingBlock.toolData ? 'tool' : 'prompt';
              const blockData = currentPendingBlock.toolData || currentPendingBlock.promptData;
              
              console.log(`🔍 [VMCPEditor] Creating atomic block:`, {
                blockType,
                blockData,
                currentPendingBlock
              });
              
              const defaultValues = extractDefaultValues(blockData, blockType);
              
              const block = createAtomicBlock(
                startLine,
                startColumn,
                endLine,
                endColumn,
                blockType,
                currentPendingBlock.server,
                currentPendingBlock.label,
                change.text,
                blockData,
                defaultValues
              );
              
              // Mark as newly inserted to prevent position updates
              newlyInsertedBlocksRef.current.add(block.id);
              
              registerAtomicBlock(block);
              console.log(`✅ [VMCPEditor] Atomic block created:`, block);
              
              // Get current cursor position before moving
              const currentPosition = editor.getPosition();
              console.log(`📍 [VMCPEditor] Current cursor position:`, currentPosition);
              console.log(`📍 [VMCPEditor] Moving cursor to atomic block end:`, {
                lineNumber: block.endLine,
                column: block.endColumn
              });
              
              // Move cursor to the end of the atomic block to prevent editing inside
              editor.setPosition({
                lineNumber: block.endLine,
                column: block.endColumn
              });
              
              // Clear the newly inserted flag after a delay to allow normal position updates
              setTimeout(() => {
                newlyInsertedBlocksRef.current.delete(block.id);
                console.log(`🔄 [VMCPEditor] Cleared newly inserted flag for block:`, block.id);
              }, 300);
              
              // Save atomic blocks after creation
              saveAtomicBlocks();
              
              // Reset creation flag after everything is done
              setTimeout(() => {
                isCreatingAtomicBlockRef.current = false;
                console.log(`🔄 [VMCPEditor] Reset creation flag`);
              }, 100);
            }, 50);
          }
          
          // Handle atomic block deletion
          if ((!change.text || change.text === '') && !isDeletingAtomicBlock) {
            const startLine = change.range.startLineNumber;
            const startColumn = change.range.startColumn;
            const endLine = change.range.endLineNumber;
            const endColumn = change.range.endColumn;
            
            // Find atomic blocks that overlap with this deletion
            const affectedBlocks = findAtomicBlocksInRange(startLine, startColumn, endLine, endColumn);
            
            if (affectedBlocks.length > 0) {
              console.log(`🗑️ [VMCPEditor] Deletion detected, affected atomic blocks:`, affectedBlocks);
              
              // Prevent recursive deletion
              isDeletingAtomicBlock = true;
              
              // For each affected block, delete the entire block
              affectedBlocks.forEach(block => {
                const model = editor.getModel();
                if (model) {
                  const blockRange = new monaco.Range(
                    block.startLine,
                    block.startColumn,
                    block.endLine,
                    block.endColumn
                  );
                  
                  // Delete the entire atomic block
                  model.pushEditOperations([], [{
                    range: blockRange,
                    text: '',
                    forceMoveMarkers: true
                  }], () => null);
                  
                  // Remove from our tracking
                  atomicBlocksRef.current.delete(block.id);
                  console.log(`✅ [VMCPEditor] Atomic block deleted:`, block.id);
                }
              });
              
              // Update decorations after deletion
              updateAtomicBlockDecorations();
              
              // Save atomic blocks after deletion
              saveAtomicBlocks();
              
              // Reset deletion flag after a short delay
              setTimeout(() => {
                isDeletingAtomicBlock = false;
              }, 100);
            } else {
              // No atomic blocks affected, but we still need to update positions
              updateAtomicBlockPositions(change);
            }
          } else if (!isDeletingAtomicBlock) {
            // Text insertion or modification - update positions
            updateAtomicBlockPositions(change);
          }
        }
      }
    });

    // Register completion provider on the active model language
    const targetLanguageId = language || languageConfig.languageId;
    const completionProvider = monaco.languages.registerCompletionItemProvider(
      targetLanguageId,
      {
        triggerCharacters: ["@", "."],
        provideCompletionItems: (model: any, position: any) => {
          const textUntilPosition = model.getValueInRange({
            startLineNumber: position.lineNumber,
            startColumn: 1,
            endLineNumber: position.lineNumber,
            endColumn: position.column,
          });

          const word = model.getWordUntilPosition(position);
          const range = {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: word.startColumn,
            endColumn: word.endColumn,
          };

          const suggestions: any[] = [];

          // Check what user is typing
          const isAtSymbol = /@$/.test(textUntilPosition);
          const isToolPrefix = /@tool\.$/.test(textUntilPosition);
          const isPromptPrefix = /@prompt\.$/.test(textUntilPosition);
          const isResourcePrefix = /@resource\.$/.test(textUntilPosition);
          const isVarPrefix = /@param\.$/.test(textUntilPosition);
          const isEnvPrefix = /@config\.$/.test(textUntilPosition);

          console.log(`🔍 [Completion] Text: "${textUntilPosition}"`, {
            isAtSymbol,
            isToolPrefix,
            isPromptPrefix,
            isResourcePrefix,
            isVarPrefix,
            isEnvPrefix
          });

          // @ symbol - show main categories
          if (isAtSymbol) {
            const atRange = {
              startLineNumber: position.lineNumber,
              endLineNumber: position.lineNumber,
              startColumn: position.column - 1,
              endColumn: position.column,
            };

            suggestions.push(
              {
                label: "@tool",
                insertText: "@tool.",
                kind: monaco.languages.CompletionItemKind.Keyword,
                detail: "Access tools",
                documentation: "Call tools from MCP servers or custom tools",
                range: atRange,
                command: { id: "editor.action.triggerSuggest", title: "Re-trigger completion" },
              },
              {
                label: "@prompt", 
                insertText: "@prompt.",
                kind: monaco.languages.CompletionItemKind.Keyword,
                detail: "Access prompts",
                documentation: "Execute prompts from MCP servers or custom prompts",
                range: atRange,
                command: { id: "editor.action.triggerSuggest", title: "Re-trigger completion" },
              },
              {
                label: "@resource",
                insertText: "@resource.",
                kind: monaco.languages.CompletionItemKind.Keyword,
                detail: "Access resources",
                documentation: "Reference resources from MCP servers or custom resources",
                range: atRange,
                command: { id: "editor.action.triggerSuggest", title: "Re-trigger completion" },
              },
              {
                label: "@param",
                insertText: "@param.",
                kind: monaco.languages.CompletionItemKind.Keyword,
                detail: "Access variables",
                documentation: "Use local variables defined in the current context",
                range: atRange,
                command: { id: "editor.action.triggerSuggest", title: "Re-trigger completion" },
              },
              {
                label: "@config",
                insertText: "@config.",
                kind: monaco.languages.CompletionItemKind.Keyword,
                detail: "Access environment variables",
                documentation: "Use environment variables",
                range: atRange,
                command: { id: "editor.action.triggerSuggest", title: "Re-trigger completion" },
              }
            );

            return { suggestions };
          }

          // @tool. - show available tools
          if (isToolPrefix) {
            if (!completionData.toolCompletions || completionData.toolCompletions.length === 0) {
              suggestions.push({
                label: "No tools available",
                insertText: "",
                kind: monaco.languages.CompletionItemKind.Snippet,
                detail: "Configure tools in your VMCP settings",
                documentation: "Add tools through MCP servers or custom tools configuration",
                range,
              });
            } else {
              (completionData.toolCompletions || []).forEach(tool => {
                const insertText = buildToolSnippet(tool.toolData);
                suggestions.push({
                  label: tool.label,
                  insertText,
                  insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
                  kind: monaco.languages.CompletionItemKind.Function,
                  detail: `[Tool] ${tool.server}`,
                  documentation: tool.description,
                  range,
                  // Store tool data for atomic block creation
                  toolData: tool.toolData,
                  server: tool.server
                });
              });
            }
            return { suggestions };
          }

          // @prompt. - show available prompts  
          if (isPromptPrefix) {
            if (!completionData.promptCompletions || completionData.promptCompletions.length === 0) {
              suggestions.push({
                label: "No prompts available",
                insertText: "",
                kind: monaco.languages.CompletionItemKind.Snippet,
                detail: "Configure prompts in your VMCP settings",
                documentation: "Add prompts through MCP servers or custom prompts configuration",
                range,
              });
            } else {
              (completionData.promptCompletions || []).forEach(prompt => {
                const insertText = buildPromptSnippet(prompt.promptData);
                suggestions.push({
                  label: prompt.label,
                  insertText,
                  insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
                  kind: monaco.languages.CompletionItemKind.Snippet,
                  detail: `[Prompt] ${prompt.server}`,
                  documentation: prompt.description,
                  range,
                  // Store prompt data for atomic block creation
                  promptData: prompt.promptData,
                  server: prompt.server
                });
              });
            }
            return { suggestions };
          }

          // @resource. - show available resources
          if (isResourcePrefix) {
            if (!completionData.resourceCompletions || completionData.resourceCompletions.length === 0) {
              suggestions.push({
                label: "No resources available",
                insertText: "",
                kind: monaco.languages.CompletionItemKind.Snippet,
                detail: "Configure resources in your VMCP settings",
                documentation: "Add resources through MCP servers or custom resources configuration",
                range,
              });
            } else {
              (completionData.resourceCompletions || []).forEach(resource => {
                suggestions.push({
                  label: resource.label,
                  insertText: resource.label,
                  kind: monaco.languages.CompletionItemKind.File,
                  detail: `[Resource] ${resource.server}`,
                  documentation: resource.description,
                  range,
                });
              });
            }
            return { suggestions };
          }

          // @var. - show context variables
          if (isVarPrefix) {
            if (!completionData.varCompletions || completionData.varCompletions.length === 0) {
              suggestions.push({
                label: "No variables available",
                insertText: "",
                kind: monaco.languages.CompletionItemKind.Snippet,
                detail: "No variables defined in current context",
                documentation: "Define variables in your prompt or tool configuration",
                range,
              });
            } else {
              (completionData.varCompletions || []).forEach(variable => {
                suggestions.push({
                  label: variable.label,
                  insertText: variable.label,
                  kind: monaco.languages.CompletionItemKind.Variable,
                  detail: `[Variable] ${editKey || 'context'}`,
                  documentation: variable.description,
                  range,
                });
              });
            }
            return { suggestions };
          }

          // @env. - show environment variables
          if (isEnvPrefix) {
            if (!completionData.envCompletions || completionData.envCompletions.length === 0) {
              suggestions.push({
                label: "No environment variables available",
                insertText: "",
                kind: monaco.languages.CompletionItemKind.Snippet,
                detail: "Configure environment variables in your VMCP settings",
                documentation: "Add environment variables to your configuration",
                range,
              });
            } else {
              (completionData.envCompletions || []).forEach(env => {
                suggestions.push({
                  label: env.label,
                  insertText: env.label,
                  kind: monaco.languages.CompletionItemKind.EnumMember,
                  detail: "[Environment Variable]",
                  documentation: env.description,
                  range,
                });
              });
            }
            return { suggestions };
          }

          return { suggestions };
        },
        resolveCompletionItem: (item: any) => {
          // Store the completion item data for atomic block creation
          if (item.toolData || item.promptData) {
            pendingAtomicBlockRef.current = item;
            console.log(`🔍 [VMCPEditor] Set pending atomic block:`, item.label);
          }
          return item;
        }
      }
    );

    providersRef.current.push(completionProvider);

    // Register hover provider for additional help
    const hoverProvider = monaco.languages.registerHoverProvider(targetLanguageId, {
      provideHover: (model: any, position: any) => {
        const line = model.getLineContent(position.lineNumber);
        const cursorPos = position.column - 1;

        // Find VMCP expressions in the line
        const vmcpPattern = /(@(?:env|var|tool|prompt|resource)\.\w+(?:\.\w+)?(?:\([^)]*\))?)/g;
        let match;
        let foundExpression = null;

        while ((match = vmcpPattern.exec(line)) !== null) {
          const startPos = match.index;
          const endPos = match.index + match[0].length;
          
          // Check if cursor is within this expression
          if (cursorPos >= startPos && cursorPos <= endPos) {
            foundExpression = { start: startPos, end: endPos, text: match[0] };
            break;
          }
        }

        if (!foundExpression) return null;

        const expression = foundExpression.text;
        const range = new monaco.Range(
          position.lineNumber,
          foundExpression.start + 1,
          position.lineNumber,
          foundExpression.end + 1
        );

        // Parse the expression to determine type and details
        if (expression.startsWith('@config.')) {
          const envName = expression.substring(5);
          const envVar = completionData.envCompletions?.find(env => env.label === envName);
          
          return {
            range,
            contents: [
              { value: `**🌍 Environment Variable**: \`${envName}\`` },
              { value: `**Description**: ${envVar?.description || `Environment variable: ${envName}`}` },
              { value: 'Access environment variables with @config.VARIABLE_NAME' },
              { value: '---' },
              { value: '**Commands:**' },
              { value: '• Click to configure • Test: `@test.config.${envName}`' }
            ]
          };
        }

        if (expression.startsWith('@param.')) {
          const varName = expression.substring(5);
          const variable = completionData.varCompletions?.find(v => v.label === varName);
          
          return {
            range,
            contents: [
              { value: `**📝 Local Variable**: \`${varName}\`` },
              { value: `**Description**: ${variable?.description || `Variable: ${varName}`}` },
              { value: `**Context**: ${editKey || 'unknown'}` },
              { value: '---' },
              { value: '**Commands:**' },
              { value: '• Click to configure • Test: `@test.param.${varName}`' }
            ]
          };
        }

        if (expression.startsWith('@tool.')) {
          const toolMatch = expression.match(/@tool\.([^.]+)\.([^(]+)/);
          if (toolMatch) {
            const [, serverName, toolName] = toolMatch;
            const tool = completionData.toolCompletions?.find(t => 
              t.label === `${serverName}.${toolName}`
            );
            
            if (tool && tool.toolData) {
              const toolData = tool.toolData;
              const contents = [
                { value: `**🔧 Tool**: \`${toolName}\`` },
                { value: `**Server**: ${serverName}` },
                { value: `**Description**: ${toolData.description || 'No description available'}` }
              ];

              // Add parameter information if available
              if (toolData.inputSchema?.properties) {
                const properties = toolData.inputSchema.properties;
                const required = toolData.inputSchema.required || [];
                
                if (Object.keys(properties).length > 0) {
                  contents.push({ value: '**Parameters:**' });
                  
                  Object.entries(properties).forEach(([paramName, schema]: [string, any]) => {
                    const isRequired = required.includes(paramName);
                    const paramType = schema.type || 'any';
                    const paramDesc = schema.description || 'No description';
                    const status = isRequired ? '🔴 **Required**' : '⚪ *Optional*';
                    
                    contents.push({ 
                      value: `- \`${paramName}\` (${paramType}) ${status}` 
                    });
                    if (paramDesc !== 'No description') {
                      contents.push({ 
                        value: `  ${paramDesc}` 
                      });
                    }
                  });
                } else {
                  contents.push({ value: '*No parameters required*' });
                }
              } else {
                contents.push({ value: '*No parameters required*' });
              }

              contents.push({ value: '---' });
              contents.push({ value: '**Commands:**' });
              contents.push({ value: '• Click to configure parameters • Test: `@test.tool.${serverName}.${toolName}`' });

              return { range, contents };
            }
          }
        }

        if (expression.startsWith('@prompt.')) {
          const promptMatch = expression.match(/@prompt\.([^.]+)\.([^(]+)/);
          if (promptMatch) {
            const [, serverName, promptName] = promptMatch;
            const prompt = completionData.promptCompletions?.find(p => 
              p.label === `${serverName}.${promptName}`
            );
            
            if (prompt && prompt.promptData) {
              const promptData = prompt.promptData;
              const contents = [
                { value: `**💬 Prompt**: \`${promptName}\`` },
                { value: `**Server**: ${serverName}` },
                { value: `**Description**: ${promptData.description || 'No description available'}` }
              ];

              // Add argument information if available
              if (promptData.arguments && promptData.arguments.length > 0) {
                contents.push({ value: '**Arguments:**' });
                
                promptData.arguments.forEach((arg: any) => {
                  const isRequired = arg.required !== false;
                  const status = isRequired ? '🔴 **Required**' : '⚪ *Optional*';
                  
                  contents.push({ 
                    value: `- \`${arg.name}\` ${status}` 
                  });
                  if (arg.description && arg.description !== 'No description') {
                    contents.push({ 
                      value: `  ${arg.description}` 
                    });
                  }
                });
              } else {
                contents.push({ value: '*No arguments required*' });
              }

              contents.push({ value: '---' });
              contents.push({ value: '**Commands:**' });
              contents.push({ value: '• Click to configure parameters • Test: `@test.prompt.${serverName}.${promptName}`' });

              return { range, contents };
            }
          }
        }

        if (expression.startsWith('@resource.')) {
          const resourceMatch = expression.match(/@resource\.([^.]+)\.(.+)/);
          if (resourceMatch) {
            const [, serverName, resourceName] = resourceMatch;
            const resource = completionData.resourceCompletions?.find(r => 
              r.label === `${serverName}.${resourceName}`
            );
            
            return {
              range,
              contents: [
                { value: `**📄 Resource**: \`${resourceName}\`` },
                { value: `**Server**: ${serverName}` },
                { value: `**Description**: ${resource?.description || `Resource from ${serverName} server`}` },
                { value: '---' },
                { value: '**Commands:**' },
                { value: '• Click to configure • Test: `@test.resource.${serverName}.${resourceName}`' }
              ]
            };
          }
        }

        return null;
      }
    });

    providersRef.current.push(hoverProvider);

    // Add click handler for atomic blocks - only on mouse up to avoid selection interference
    let mouseDownPosition: any = null;
    let isSelecting = false;
    
    editor.onMouseDown((e: any) => {
      if (e.target.type === monaco.editor.MouseTargetType.CONTENT_TEXT) {
        console.log(`🚨 [VMCPEditor] Mouse down`);
        mouseDownPosition = e.target.position;
        isSelecting = false;
      }
    });
    
    editor.onMouseMove((e: any) => {
      // console.log(`🚨 [VMCPEditor] Mouse move`);
      if (mouseDownPosition) {
        isSelecting = true;
      }
    });
    
    editor.onMouseUp((e: any) => {
      console.log(`🚨 [VMCPEditor] Mouse up`);
      if (e.target.type === monaco.editor.MouseTargetType.CONTENT_TEXT && mouseDownPosition) {
        const position = e.target.position;
        
        // Use a small delay to ensure selection state is properly set
        setTimeout(() => {
          const selection = editor.getSelection();
          const hasSelection = selection && !selection.isEmpty();
          
          // Only open modal if it's a genuine click (not selection) and no active selection
          const isClick = !isSelecting && !hasSelection && 
                         mouseDownPosition.lineNumber === position.lineNumber && 
                         Math.abs(mouseDownPosition.column - position.column) <= 1;
          console.log(`🚨 [VMCPEditor] isClick:`, isClick);
          if (isClick) {
            const block = findAtomicBlockAtPosition(position.lineNumber, position.column);
            
            if (block) {
              console.log(`🚨 [VMCPEditor] MODAL OPENING - Called from mouse click handler (onMouseUp)`);
              handleAtomicBlockClick(block);
            }
          }
          
          mouseDownPosition = null;
          isSelecting = false;
        }, 10);
      }
    });

    console.log(`✅ [VMCPEditor] Providers registered:`, providersRef.current.length);
  }, [completionData, languageConfig.languageId, editKey, createAtomicBlock, registerAtomicBlock, findAtomicBlockAtPosition, findAtomicBlocksInRange, handleAtomicBlockClick, updateAtomicBlockDecorations, updateAtomicBlockPositions, saveAtomicBlocks]);

  // Handle Monaco editor mount
  const handleEditorMount = useCallback(async (editor: any, monaco: any) => {
    console.log(`🎯 [VMCPEditor] Editor mounted`);
    
    monacoRef.current = { editor, monaco };

    try {
      // Register custom language if not already registered
      const existingLanguages = monaco.languages.getLanguages();
      if (!existingLanguages.some((l: any) => l.id === languageConfig.languageId)) {
        monaco.languages.register({ id: languageConfig.languageId });
        console.log(`📝 [VMCPEditor] Language '${languageConfig.languageId}' registered`);
      }

      // Set tokenizer
      monaco.languages.setMonarchTokensProvider(languageConfig.languageId, languageConfig.monarch);

      // Define and apply theme
      monaco.editor.defineTheme(languageConfig.themeId, languageConfig.theme);
      monaco.editor.setTheme(languageConfig.themeId);

      // Set model language (override with explicit language if provided)
      const model = editor.getModel();
      if (model) {
        monaco.editor.setModelLanguage(model, language || languageConfig.languageId);
      }

      // Register providers after a short delay
      setTimeout(() => {
        registerProviders(editor, monaco);
        // Restore atomic blocks from saved data
        restoreAtomicBlocks();
        // Update decorations after providers are registered
        updateAtomicBlockDecorations();
        // Prevent direct editing of atomic block parameters
        preventAtomicBlockEditing(editor);
      }, 100);

      console.log(`✅ [VMCPEditor] Setup complete`);
    } catch (error) {
      console.error(`❌ [VMCPEditor] Setup failed:`, error);
    }
  }, [language, languageConfig, registerProviders, updateAtomicBlockDecorations, restoreAtomicBlocks, preventAtomicBlockEditing]);

  // Re-register providers when completion data changes
  useEffect(() => {
    const { editor, monaco } = monacoRef.current || {};
    if (editor && monaco) {
      console.log(`🔄 [VMCPEditor] Completion data changed, re-registering providers`);
      registerProviders(editor, monaco);
    }
  }, [completionData, registerProviders]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      providersRef.current.forEach(provider => {
        try {
          provider?.dispose?.();
        } catch (e) {
          console.warn('Cleanup failed for provider:', e);
        }
      });
      providersRef.current = [];
      
      // Clear decorations
      const { editor } = monacoRef.current || {};
      if (editor) {
        decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);
      }
      decorationsRef.current = [];
      
      // Clear any pending decoration update
      if (decorationUpdateTimeoutRef.current) {
        clearTimeout(decorationUpdateTimeoutRef.current);
      }
      
      // Clear any pending position update
      if (positionUpdateTimeoutRef.current) {
        clearTimeout(positionUpdateTimeoutRef.current);
      }
    };
  }, []);

  return (
    <div className={className}>
      <style dangerouslySetInnerHTML={{__html: `
        .atomic-block-highlight {
          background-color: rgba(59, 130, 246, 0.1) !important;
          border: 1px solid rgba(59, 130, 246, 0.3) !important;
          border-radius: 4px !important;
          padding: 1px 2px !important;
          margin: 0 1px !important;
          cursor: pointer !important;
          transition: all 0.2s ease !important;
        }

        .atomic-block-highlight:hover {
          background-color: rgba(59, 130, 246, 0.2) !important;
          border-color: rgba(59, 130, 246, 0.5) !important;
        }

        .monaco-editor .view-overlays .current-line {
          background-color: transparent !important;
        }

        /* JSON syntax highlighting */
        .json-editor {
          font-family: Monaco, Menlo, "Ubuntu Mono", monospace !important;
          line-height: 1.4 !important;
          tab-size: 2 !important;
        }

        .json-editor:focus {
          outline: none !important;
          border-color: #3b82f6 !important;
          box-shadow: 0 0 0 1px #3b82f6 !important;
        }

        /* JSON syntax highlighting colors */
        .json-key {
          color: #9cdcfe !important;
        }

        .json-string {
          color: #ce9178 !important;
        }

        .json-number {
          color: #b5cea8 !important;
        }

        .json-boolean {
          color: #569cd6 !important;
        }

        .json-null {
          color: #808080 !important;
        }
      `}} />
      <MonacoEditor
        height={height}
        language={language || "plaintext"}
        value={value}
        onChange={(val: string | undefined) => onChange(val ?? "")}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: "off",
          glyphMargin: false,
          folding: false,
          lineDecorationsWidth: 0,
          lineNumbersMinChars: 0,
          renderLineHighlight: "none",
          scrollBeyondLastLine: false,
          wordWrap: "on",
          readOnly: readOnly,
          suggest: {
            showIcons: true,
            showWords: false,
            showSnippets: true,
          },
          tabSize: 2,
          renderWhitespace: "selection",
          automaticLayout: true,
          acceptSuggestionOnCommitCharacter: true,
          acceptSuggestionOnEnter: "on",
          quickSuggestions: {
            other: true,
            comments: false,
            strings: false
          }
        }}
        onMount={handleEditorMount}
      />

      {/* Help text */}
      {showSyntaxGuide && (
        <div className="mt-2 text-xs text-muted-foreground">
          <p className="font-medium mb-2">VMCP Syntax Guide:</p>
          
          {editKey && (
            <div className="mb-3 p-2 bg-muted/50 rounded border-l-2 border-primary text-xs">
              <strong>Editing Context:</strong>{" "}
              {editKey === "system_prompt" 
                ? "System Prompt" 
                : editKey === "custom_prompt" 
                  ? `Custom Prompt ${editIndex != null ? `#${editIndex + 1}` : ''}`
                  : editKey === "custom_tool"
                    ? `Custom Tool ${editIndex != null ? `#${editIndex + 1}` : ''}`
                    : "Unknown"}
            </div>
          )}

          <div className="space-y-1">
            <div><code className="bg-muted px-1 py-0.5 rounded">@</code> - Trigger category selection</div>
            <div><code className="bg-muted px-1 py-0.5 rounded">@config.VAR_NAME</code> - Environment variables ({completionData.envCompletions.length} available)</div>
            <div><code className="bg-muted px-1 py-0.5 rounded">@param.name</code> - Context variables ({completionData.varCompletions.length} available)</div>
            <div><code className="bg-muted px-1 py-0.5 rounded">@tool.server.name()</code> - Tool calls ({completionData.toolCompletions.length} available)</div>
            <div><code className="bg-muted px-1 py-0.5 rounded">@prompt.server.name()</code> - Prompt execution ({completionData.promptCompletions.length} available)</div>
            <div><code className="bg-muted px-1 py-0.5 rounded">@resource.server.name</code> - Resource references ({completionData.resourceCompletions.length} available)</div>
          </div>
          
          <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-950/20 rounded border-l-2 border-blue-500 text-xs">
            <strong>💡 Atomic Blocks:</strong> Click on any inserted tool/prompt to configure parameters. 
            Atomic blocks behave as single units when deleting.
          </div>
        </div>
      )}

      {/* Parameter Modal */}
      <ParameterModal
        isOpen={modalState.isOpen}
        onClose={() => setModalState({ isOpen: false, block: null })}
        block={modalState.block}
        onSave={handleModalSave}
      />
    </div>
  );
};

export default VMCPMonacoEditor;