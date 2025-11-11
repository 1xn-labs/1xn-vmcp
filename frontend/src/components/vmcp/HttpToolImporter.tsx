
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Upload, FileText, Globe, Check, X, Loader2, Plus, Trash2, ChevronRight, ChevronDown, Folder } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import VMCPMonacoEditor from '@/components/editor/VMCPMonacoEditor';

interface CollectionVariable {
  key: string;
  value: string;
  description?: string;
  type?: string;
}

interface CollectionMetadata {
  name: string;
  description?: string;
  variables: CollectionVariable[];
  baseUrl?: string;
}

interface HttpTool {
  name: string;
  method: string;
  url: string;
  description?: string;
  headers?: Array<{ key: string; value: string }>;
  queryParams?: Array<{ key: string; value: string }>;
  body?: string | object;
  auth?: {
    type: 'none' | 'bearer' | 'apikey' | 'basic';
    token?: string;
    apiKey?: string;
    username?: string;
    password?: string;
  };
  responseSchema?: any;
  groupPath?: string[];
  tags?: string[];
  collectionMetadata?: CollectionMetadata;
  parameters?: Array<{ name: string; description: string; required: boolean; type: string }>;
}

interface HttpToolImporterProps {
  onImport: (tools: HttpTool[]) => void;
  onClose: () => void;
}

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];

// Function to extract variables from text and create parameters
const extractVariables = (text: string): Array<{ name: string; description: string; required: boolean; type: string }> => {
  const variables = new Set<string>();
  const variableRegex = /\{\{([^}]+)\}\}/g;
  let match;
  
  while ((match = variableRegex.exec(text)) !== null) {
    variables.add(match[1]);
  }
  
  return Array.from(variables).map(varName => ({
    name: varName,
    description: `Variable: ${varName}`,
    required: true,
    type: 'string'
  }));
};

// Function to extract path parameters from URL
const extractPathParams = (url: string): Array<{ name: string; description: string; required: boolean; type: string }> => {
  const pathParams = new Set<string>();
  const pathParamRegex = /:([a-zA-Z_][a-zA-Z0-9_]*)/g;
  let match;
  
  while ((match = pathParamRegex.exec(url)) !== null) {
    pathParams.add(match[1]);
  }
  
  return Array.from(pathParams).map(paramName => ({
    name: paramName,
    description: `Path parameter: ${paramName}`,
    required: true,
    type: 'string'
  }));
};

// Function to extract query parameters from URL
const extractQueryParams = (url: string): Array<{ name: string; description: string; required: boolean; type: string; defaultValue?: string }> => {
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

// Function to create parameters for a tool
const createToolParameters = (tool: HttpTool): Array<{ name: string; description: string; required: boolean; type: string }> => {
  const parameters = new Map<string, { name: string; description: string; required: boolean; type: string }>();
  
  // Extract from URL
  const urlVars = extractVariables(tool.url);
  const pathParams = extractPathParams(tool.url);
  const queryParams = extractQueryParams(tool.url);
  
  urlVars.forEach(param => parameters.set(param.name, param));
  pathParams.forEach(param => parameters.set(param.name, param));
  queryParams.forEach(param => parameters.set(param.name, param));
  
  // Extract from headers
  tool.headers?.forEach(header => {
    const headerVars = extractVariables(header.value);
    headerVars.forEach(param => parameters.set(param.name, param));
  });
  
  // Extract from query parameters
  tool.queryParams?.forEach(param => {
    const paramVars = extractVariables(param.value);
    paramVars.forEach(variable => parameters.set(variable.name, variable));
  });
  
  // Extract from body
  if (tool.body) {
    try {
      // Try to parse as JSON first
      const bodyObj = typeof tool.body === 'string' ? JSON.parse(tool.body) : tool.body;
      const bodyVars = extractVariablesFromJson(bodyObj);
      bodyVars.forEach(param => parameters.set(param.name, param));
    } catch (e) {
      // If not JSON, treat as string and look for variables
      const bodyStr = typeof tool.body === 'string' ? tool.body : JSON.stringify(tool.body);
      const bodyVars = extractVariables(bodyStr);
      bodyVars.forEach(param => parameters.set(param.name, param));
    }
  }
  
  // Extract from auth fields
  if (tool.auth?.token) {
    const authVars = extractVariables(tool.auth.token);
    authVars.forEach(param => parameters.set(param.name, param));
  }
  if (tool.auth?.apiKey) {
    const authVars = extractVariables(tool.auth.apiKey);
    authVars.forEach(param => parameters.set(param.name, param));
  }
  if (tool.auth?.username) {
    const authVars = extractVariables(tool.auth.username);
    authVars.forEach(param => parameters.set(param.name, param));
  }
  if (tool.auth?.password) {
    const authVars = extractVariables(tool.auth.password);
    authVars.forEach(param => parameters.set(param.name, param));
  }
  
  return Array.from(parameters.values());
};

export default function HttpToolImporter({ onImport, onClose }: HttpToolImporterProps) {
  const [activeTab, setActiveTab] = useState('openapi');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // HTTP Method tab state
  const [httpTool, setHttpTool] = useState<HttpTool>({
    name: '',
    method: 'GET',
    url: '',
    description: '',
    headers: [],
    queryParams: [],
    body: {},
    auth: { type: 'none' },
    responseSchema: {}
  });

  // OpenAPI/Postman tabs state
  const [openApiSpec, setOpenApiSpec] = useState<any>(null);
  const [postmanCollection, setPostmanCollection] = useState<any>(null);
  const [selectedEndpoints, setSelectedEndpoints] = useState<Set<string>>(new Set());
  const [endpoints, setEndpoints] = useState<HttpTool[]>([]);
  const [originalCollection, setOriginalCollection] = useState<any>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [treeStructure, setTreeStructure] = useState<any[]>([]);

  // Update tree structure when expanded folders or endpoints change
  useEffect(() => {
    if (endpoints.length > 0) {
      const tree = buildTreeStructure(endpoints);
      setTreeStructure(treeToArray(tree));
    }
  }, [expandedFolders, endpoints, selectedEndpoints]);

  // Function to build tree structure from endpoints
  const buildTreeStructure = (endpoints: HttpTool[]) => {
    const tree: any = {};
    
    endpoints.forEach((endpoint, index) => {
      const path = endpoint.groupPath || [];
      let current = tree;
      
      // Build nested structure
      path.forEach((folder, folderIndex) => {
        if (!current[folder]) {
          current[folder] = {
            type: 'folder',
            name: folder,
            children: {},
            endpoints: [],
            path: path.slice(0, folderIndex + 1)
          };
        }
        current = current[folder].children;
      });
      
      // Add endpoint to the deepest folder
      const deepestFolder = path.reduce((acc, folder) => {
        return acc[folder] || acc;
      }, tree);
      if (deepestFolder.endpoints) {
        deepestFolder.endpoints.push({ ...endpoint, index });
      }
    });
    
    return tree;
  };

  // Function to convert tree to array for rendering
  const treeToArray = (tree: any, level = 0): any[] => {
    const result: any[] = [];
    
    Object.keys(tree).forEach(key => {
      const item = tree[key];
      if (item.type === 'folder') {
        const selectedCount = getSelectedCountInFolder(item);
        const isExpanded = expandedFolders.has(item.path.join('/'));
        
        result.push({
          ...item,
          level,
          selectedCount,
          isExpanded
        });
        
        if (isExpanded) {
          result.push(...treeToArray(item.children, level + 1));
          result.push(...item.endpoints.map((endpoint: any) => ({
            ...endpoint,
            level: level + 1,
            type: 'endpoint'
          })));
        }
      }
    });
    
    return result;
  };

  // Function to get selected count in a folder
  const getSelectedCountInFolder = (folder: any): number => {
    let count = 0;
    
    // Count selected endpoints in this folder
    folder.endpoints?.forEach((endpoint: any) => {
      if (selectedEndpoints.has(endpoint.index.toString())) {
        count++;
      }
    });
    
    // Count selected endpoints in subfolders
    Object.values(folder.children || {}).forEach((child: any) => {
      if (child.type === 'folder') {
        count += getSelectedCountInFolder(child);
      }
    });
    
    return count;
  };

  // Function to toggle folder expansion
  const toggleFolder = (path: string) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedFolders(newExpanded);
  };

  // Function to select all endpoints in a folder
  const selectAllInFolder = (folder: any) => {
    const newSelected = new Set(selectedEndpoints);
    
    // Add all endpoints in this folder
    folder.endpoints?.forEach((endpoint: any) => {
      newSelected.add(endpoint.index.toString());
    });
    
    // Add all endpoints in subfolders
    const addFromSubfolders = (subfolder: any) => {
      subfolder.endpoints?.forEach((endpoint: any) => {
        newSelected.add(endpoint.index.toString());
      });
      Object.values(subfolder.children || {}).forEach((child: any) => {
        if (child.type === 'folder') {
          addFromSubfolders(child);
        }
      });
    };
    
    Object.values(folder.children || {}).forEach((child: any) => {
      if (child.type === 'folder') {
        addFromSubfolders(child);
      }
    });
    
    setSelectedEndpoints(newSelected);
  };

  // Function to deselect all endpoints in a folder
  const deselectAllInFolder = (folder: any) => {
    const newSelected = new Set(selectedEndpoints);
    
    // Remove all endpoints in this folder
    folder.endpoints?.forEach((endpoint: any) => {
      newSelected.delete(endpoint.index.toString());
    });
    
    // Remove all endpoints in subfolders
    const removeFromSubfolders = (subfolder: any) => {
      subfolder.endpoints?.forEach((endpoint: any) => {
        newSelected.delete(endpoint.index.toString());
      });
      Object.values(subfolder.children || {}).forEach((child: any) => {
        if (child.type === 'folder') {
          removeFromSubfolders(child);
        }
      });
    };
    
    Object.values(folder.children || {}).forEach((child: any) => {
      if (child.type === 'folder') {
        removeFromSubfolders(child);
      }
    });
    
    setSelectedEndpoints(newSelected);
  };

  const handleFileUpload = (file: File, type: 'openapi' | 'postman') => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = JSON.parse(e.target?.result as string);
        if (type === 'openapi') {
          setOpenApiSpec(content);
          parseOpenApiSpec(content);
        } else {
          setPostmanCollection(content);
          parsePostmanCollection(content);
        }
        setError(null);
      } catch (err) {
        setError('Invalid JSON file');
      }
    };
    reader.readAsText(file);
  };

  const parseOpenApiSpec = (spec: any) => {
    const tools: HttpTool[] = [];
    const paths = spec.paths || {};
    
    Object.entries(paths).forEach(([path, methods]: [string, any]) => {
      Object.entries(methods).forEach(([method, operation]: [string, any]) => {
        if (typeof operation === 'object' && operation.operationId) {
          const tool: HttpTool = {
            name: operation.operationId || `${method.toUpperCase()} ${path}`,
            method: method.toUpperCase(),
            url: path,
            description: operation.description || operation.summary || '',
            headers: [],
            queryParams: [],
            body: '',
            auth: { type: 'none' },
            responseSchema: operation.responses?.['200'] || operation.responses?.['201'],
            tags: operation.tags || []
          };

          // Parse parameters
          if (operation.parameters) {
            operation.parameters.forEach((param: any) => {
              if (param.in === 'header') {
                tool.headers?.push({ key: param.name, value: `{{${param.name.toUpperCase()}}}` });
              } else if (param.in === 'query') {
                tool.queryParams?.push({ key: param.name, value: `{{${param.name.toUpperCase()}}}` });
              }
            });
          }

          // Parse request body
          if (operation.requestBody?.content?.['application/json']) {
            tool.body = JSON.stringify(operation.requestBody.content['application/json'].schema, null, 2);
          }

          // Create parameters for the tool
          tool.parameters = createToolParameters(tool);

          tools.push(tool);
        }
      });
    });

    setEndpoints(tools);
  };

  const parsePostmanCollection = (collection: any) => {
    const tools: HttpTool[] = [];
    const collectionMetadata: CollectionMetadata = {
      name: collection.info?.name || 'Postman Collection',
      description: collection.info?.description,
      variables: collection.variable?.map((v: any) => ({
        key: v.key,
        value: v.value,
        description: v.description,
        type: v.type || 'string'
      })) || [],
      baseUrl: collection.variable?.find((v: any) => v.key === 'baseUrl')?.value
    };

    const processItems = (items: any[], groupPath: string[] = []) => {
      items.forEach((item, index) => {
        if (item.request) {
          // It's an endpoint
          const tool: HttpTool = {
            name: item.name,
            method: item.request.method || 'GET',
            url: item.request.url?.raw || item.request.url || '',
            description: item.description || '',
            headers: [],
            queryParams: [],
            body: '',
            auth: { type: 'none' },
            groupPath: [...groupPath],
            collectionMetadata
          };

          // Parse headers
          if (item.request.header) {
            tool.headers = item.request.header.map((h: any) => ({
              key: h.key,
              value: h.value || `{{${h.key.toUpperCase()}}}`
            }));
          }

          // Parse query parameters
          if (item.request.url?.query) {
            tool.queryParams = item.request.url.query.map((q: any) => ({
              key: q.key,
              value: q.value || `{{${q.key.toUpperCase()}}}`
            }));
          }

          // Parse body
          if (item.request.body?.raw) {
            tool.body = item.request.body.raw;
          }

          // Parse auth
          if (item.request.auth) {
            if (item.request.auth.type === 'bearer') {
              tool.auth = {
                type: 'bearer',
                token: item.request.auth.bearer?.[0]?.value || '{{API_TOKEN}}'
              };
            } else if (item.request.auth.type === 'apikey') {
              tool.auth = {
                type: 'apikey',
                apiKey: item.request.auth.apikey?.[0]?.value || '{{API_KEY}}'
              };
            }
          }

          // Create parameters for the tool
          tool.parameters = createToolParameters(tool);

          tools.push(tool);
        } else if (item.item) {
          // It's a folder
          processItems(item.item, [...groupPath, item.name]);
        }
      });
    };

    if (collection.item) {
      processItems(collection.item);
    }

    setEndpoints(tools);
    setOriginalCollection(collection);
  };

  const handleHttpToolChange = (field: keyof HttpTool, value: any) => {
    setHttpTool(prev => ({ ...prev, [field]: value }));
  };

  const addHeader = () => {
    setHttpTool(prev => ({
      ...prev,
      headers: [...(prev.headers || []), { key: '', value: '' }]
    }));
  };

  const removeHeader = (index: number) => {
    setHttpTool(prev => ({
      ...prev,
      headers: prev.headers?.filter((_, i) => i !== index) || []
    }));
  };

  const addQueryParam = () => {
    setHttpTool(prev => ({
      ...prev,
      queryParams: [...(prev.queryParams || []), { key: '', value: '' }]
    }));
  };

  const removeQueryParam = (index: number) => {
    setHttpTool(prev => ({
      ...prev,
      queryParams: prev.queryParams?.filter((_, i) => i !== index) || []
    }));
  };

  const handleConfirmImport = () => {
    if (activeTab === 'http') {
      if (!httpTool.name || !httpTool.url) {
        setError('Name and URL are required');
        return;
      }
      
      // Create parameters for the HTTP tool
      const toolWithParams = {
        ...httpTool,
        parameters: createToolParameters(httpTool)
      };
      
      // Create body_parsed if body exists
      if (toolWithParams.body) {
        try {
          const bodyObj = typeof toolWithParams.body === 'string' ? JSON.parse(toolWithParams.body) : toolWithParams.body;
          (toolWithParams as any).body_parsed = createParsedBody(bodyObj);
        } catch (e) {
          (toolWithParams as any).body_parsed = toolWithParams.body;
        }
      }
      
      onImport([toolWithParams]);
    } else {
      const selectedTools = endpoints.filter((_, index) => selectedEndpoints.has(index.toString()));
      if (selectedTools.length === 0) {
        setError('Please select at least one endpoint');
        return;
      }
      
      // Create parameters for each selected tool
      const toolsWithParams = selectedTools.map(tool => {
        const toolWithParams = {
          ...tool,
          parameters: createToolParameters(tool)
        };
        
        // Create body_parsed if body exists
        if (toolWithParams.body) {
          try {
            const bodyObj = typeof toolWithParams.body === 'string' ? JSON.parse(toolWithParams.body) : toolWithParams.body;
            (toolWithParams as any).body_parsed = createParsedBody(bodyObj);
          } catch (e) {
            (toolWithParams as any).body_parsed = toolWithParams.body;
          }
        }
        
        return toolWithParams;
      });
      
      onImport(toolsWithParams);
    }
    onClose();
  };

  const toggleEndpointSelection = (index: number) => {
    const newSelected = new Set(selectedEndpoints);
    if (newSelected.has(index.toString())) {
      newSelected.delete(index.toString());
    } else {
      newSelected.add(index.toString());
    }
    setSelectedEndpoints(newSelected);
  };

  const renderHttpMethodTab = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="space-y-2 md:col-span-3">
          <Label htmlFor="tool-name">Tool Name *</Label>
          <Input
            id="tool-name"
            value={httpTool.name}
            onChange={(e) => handleHttpToolChange('name', e.target.value)}
            placeholder="my-http-tool"
            className="font-mono"
          />
        </div>
        <div className="space-y-2 md:col-span-1">
          <Label htmlFor="method">Method *</Label>
          <Select value={httpTool.method} onValueChange={(value) => handleHttpToolChange('method', value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {HTTP_METHODS.map(method => (
                <SelectItem key={method} value={method}>{method}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="url">URL *</Label>
        <Input
          id="url"
          value={httpTool.url}
          onChange={(e) => handleHttpToolChange('url', e.target.value)}
          placeholder="https://api.example.com/endpoint"
          className="font-mono"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          value={httpTool.description || ''}
          onChange={(e) => handleHttpToolChange('description', e.target.value)}
          placeholder="Brief description of what this tool does..."
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Headers</Label>
          <Button type="button" variant="outline" size="sm" onClick={addHeader}>
            <Plus className="h-4 w-4 mr-1" />
            Add Header
          </Button>
        </div>
        <div className="space-y-2">
          {httpTool.headers?.map((header, index) => (
            <div key={index} className="flex gap-2">
              <Input
                placeholder="Header name"
                value={header.key}
                onChange={(e) => {
                  const newHeaders = [...(httpTool.headers || [])];
                  newHeaders[index].key = e.target.value;
                  handleHttpToolChange('headers', newHeaders);
                }}
                className="font-mono"
              />
              <Input
                placeholder="Header value"
                value={header.value}
                onChange={(e) => {
                  const newHeaders = [...(httpTool.headers || [])];
                  newHeaders[index].value = e.target.value;
                  handleHttpToolChange('headers', newHeaders);
                }}
                className="font-mono"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => removeHeader(index)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Query Parameters</Label>
          <Button type="button" variant="outline" size="sm" onClick={addQueryParam}>
            <Plus className="h-4 w-4 mr-1" />
            Add Parameter
          </Button>
        </div>
        <div className="space-y-2">
          {httpTool.queryParams?.map((param, index) => (
            <div key={index} className="flex gap-2">
              <Input
                placeholder="Parameter name"
                value={param.key}
                onChange={(e) => {
                  const newParams = [...(httpTool.queryParams || [])];
                  newParams[index].key = e.target.value;
                  handleHttpToolChange('queryParams', newParams);
                }}
                className="font-mono"
              />
              <Input
                placeholder="Parameter value"
                value={param.value}
                onChange={(e) => {
                  const newParams = [...(httpTool.queryParams || [])];
                  newParams[index].value = e.target.value;
                  handleHttpToolChange('queryParams', newParams);
                }}
                className="font-mono"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => removeQueryParam(index)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="body">Request Body</Label>
        <VMCPMonacoEditor
          value={httpTool.body ? (typeof httpTool.body === 'string' ? httpTool.body : JSON.stringify(httpTool.body, null, 2)) : '{}'}
          onChange={(value) => {
            try {
              const parsed = JSON.parse(value);
              handleHttpToolChange('body', parsed);
            } catch {
              // If not valid JSON, store as string
              handleHttpToolChange('body', value);
            }
          }}
          language="json"
          height="120px"
          showSyntaxGuide={false}
        />
      </div>

      <div className="space-y-4">
        <Label>Authentication</Label>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="auth-type">Type</Label>
            <Select 
              value={httpTool.auth?.type || 'none'} 
              onValueChange={(value) => handleHttpToolChange('auth', { ...httpTool.auth, type: value })}
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

          {httpTool.auth?.type === 'bearer' && (
            <div className="space-y-2">
              <Label htmlFor="bearer-token">Token</Label>
              <Input
                id="bearer-token"
                value={httpTool.auth.token || ''}
                onChange={(e) => handleHttpToolChange('auth', { ...httpTool.auth, token: e.target.value })}
                placeholder="{{API_TOKEN}}"
                className="font-mono"
              />
            </div>
          )}

          {httpTool.auth?.type === 'apikey' && (
            <div className="space-y-2">
              <Label htmlFor="api-key">API Key</Label>
              <Input
                id="api-key"
                value={httpTool.auth.apiKey || ''}
                onChange={(e) => handleHttpToolChange('auth', { ...httpTool.auth, apiKey: e.target.value })}
                placeholder="{{API_KEY}}"
                className="font-mono"
              />
            </div>
          )}

          {httpTool.auth?.type === 'basic' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={httpTool.auth.username || ''}
                  onChange={(e) => handleHttpToolChange('auth', { ...httpTool.auth, username: e.target.value })}
                  placeholder="{{USERNAME}}"
                  className="font-mono"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={httpTool.auth.password || ''}
                  onChange={(e) => handleHttpToolChange('auth', { ...httpTool.auth, password: e.target.value })}
                  placeholder="{{PASSWORD}}"
                  className="font-mono"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="response-schema">Response Schema (JSON)</Label>
        <VMCPMonacoEditor
          value={httpTool.responseSchema ? JSON.stringify(httpTool.responseSchema, null, 2) : '{}'}
          onChange={(value) => {
            try {
              const schema = value ? JSON.parse(value) : {};
              handleHttpToolChange('responseSchema', schema);
            } catch {
              // Invalid JSON, keep as string for now
            }
          }}
          language="json"
          height="120px"
          showSyntaxGuide={false}
        />
      </div>
    </div>
  );

  const renderEndpointsList = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Available Endpoints</h3>
        <div className="text-sm text-gray-500">
          {selectedEndpoints.size} of {endpoints.length} selected
        </div>
      </div>
      
      <div className="max-h-96 overflow-y-auto space-y-1">
        {treeStructure.map((item, index) => {
          if (item.type === 'folder') {
            return (
              <div key={`folder-${item.path.join('/')}`} className="border border-border rounded-lg">
                <div 
                  className="flex items-center gap-2 p-3 hover:bg-muted/50 cursor-pointer"
                  onClick={() => toggleFolder(item.path.join('/'))}
                >
                  <div className="flex items-center gap-2 flex-1">
                    {item.isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                    <Folder className="h-4 w-4 text-blue-500" />
                    <span className="font-medium text-sm">{item.name}</span>
                    {item.selectedCount > 0 && (
                      <Badge variant="secondary" className="text-xs">
                        {item.selectedCount} selected
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        selectAllInFolder(item);
                      }}
                      className="h-6 px-2 text-xs"
                    >
                      Select All
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        deselectAllInFolder(item);
                      }}
                      className="h-6 px-2 text-xs"
                    >
                      Deselect All
                    </Button>
                  </div>
                </div>
              </div>
            );
          } else if (item.type === 'endpoint') {
            return (
              <div key={`endpoint-${item.index}`} className="flex items-start gap-3 p-3 border border-border rounded-lg hover:bg-muted/50 ml-4">
                <Checkbox
                  checked={selectedEndpoints.has(item.index.toString())}
                  onCheckedChange={() => toggleEndpointSelection(item.index)}
                  className="mt-1"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="text-xs">
                      {item.method}
                    </Badge>
                    <span className="font-medium text-sm">{item.name}</span>
                  </div>
                  <p className="text-xs text-muted-foreground break-all">{item.url}</p>
                  {item.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.description}</p>
                  )}
                </div>
              </div>
            );
          }
          return null;
        })}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-background border border-border rounded-lg shadow-xl max-w-3xl w-full max-h-full overflow-y-auto">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
              <Globe className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-foreground">Import API Collection</h2>
              <p className="text-sm text-muted-foreground">Create MCP tools from OpenAPI/Postman</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setError(null);
              onClose();
            }}
            className="h-8 w-8 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="p-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              {/* <TabsTrigger value="http">HTTP Method</TabsTrigger> */}
              <TabsTrigger value="openapi">OpenAPI JSON</TabsTrigger>
              <TabsTrigger value="postman">Postman Collection</TabsTrigger>
            </TabsList>

            {/* <TabsContent value="http" className="mt-6">
              {renderHttpMethodTab()}
            </TabsContent> */}

            <TabsContent value="openapi" className="mt-6">
              <div className="space-y-6">
                <div>
                  <Label htmlFor="openapi-file">OpenAPI Specification File</Label>
                  <Input
                    id="openapi-file"
                    type="file"
                    accept=".json,.yaml,.yml"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileUpload(file, 'openapi');
                    }}
                  />
                </div>
                {endpoints.length > 0 && renderEndpointsList()}
              </div>
            </TabsContent>

            <TabsContent value="postman" className="mt-6">
              <div className="space-y-6">
                <div>
                  <Label htmlFor="postman-file">Postman Collection File</Label>
                  <Input
                    id="postman-file"
                    type="file"
                    accept=".json"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileUpload(file, 'postman');
                    }}
                  />
                </div>
                {endpoints.length > 0 && renderEndpointsList()}
              </div>
            </TabsContent>
          </Tabs>

          {error && (
            <div className="mt-4 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button 
              variant="outline" 
              onClick={() => {
                setError(null);
                onClose();
              }} 
              disabled={loading}
            >
              Cancel
            </Button>
            <Button 
              onClick={handleConfirmImport}
              disabled={loading}
              className="flex items-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4" />
                  Import Tools
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}