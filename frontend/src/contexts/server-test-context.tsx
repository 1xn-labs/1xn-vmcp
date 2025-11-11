
import React, { createContext, useContext, useState, useCallback, useRef, ReactNode } from 'react';
import { useAuth } from '@/contexts/auth-context';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';

export interface ServerTool {
  name: string;
  description?: string;
  inputSchema?: any;
  server: string;
}

export interface ServerResource {
  uri: string;
  name?: string;
  description?: string;
  server: string;
}

export interface ServerPrompt {
  name: string;
  description?: string;
  arguments?: any;
  server: string;
}

export interface TestResult {
  success: boolean;
  result?: any;
  error?: string;
  timestamp: string;
}

interface ServerTestState {
  serverName: string | null;
  serverId: string | null;
  tools: ServerTool[];
  resources: ServerResource[];
  prompts: ServerPrompt[];
  testResults: Record<string, TestResult>;
  loading: {
    server: boolean;
    tools: boolean;
    resources: boolean;
    prompts: boolean;
  };
  loadedTabs: Set<string>;
  error: string | null;
}

interface ServerTestContextType extends ServerTestState {
  loadServer: (serverId: string) => Promise<void>;
  loadTabData: (tab: 'tools' | 'resources' | 'prompts') => Promise<void>;
  testTool: (toolName: string, arguments_: Record<string, any>) => Promise<void>;
  testResource: (resourceUri: string) => Promise<void>;
  testPrompt: (promptName: string, arguments_: Record<string, any>) => Promise<void>;
  clearTestResults: () => void;
  clearError: () => void;
}

const ServerTestContext = createContext<ServerTestContextType | undefined>(undefined);

interface ServerTestProviderProps {
  children: ReactNode;
}

export function ServerTestProvider({ children }: ServerTestProviderProps) {
  const { isAuthenticated, user } = useAuth();
  const { error: toastError } = useToast();
  const [state, setState] = useState<ServerTestState>({
    serverName: null,
    serverId: null,
    tools: [],
    resources: [],
    prompts: [],
    testResults: {},
    loading: {
      server: false,
      tools: false,
      resources: false,
      prompts: false,
    },
    loadedTabs: new Set(),
    error: null,
  });

  // Add refs to prevent duplicate calls
  const loadingRef = useRef<Set<string>>(new Set());

  const loadServer = useCallback(async (serverId: string) => {
    if (!isAuthenticated || !user) {
      return;
    }

    if (loadingRef.current.has('server')) {
      return;
    }

    try {
      loadingRef.current.add('server');
      setState(prev => ({
        ...prev,
        serverId,
        loading: { ...prev.loading, server: true },
        error: null,
      }));

      // Simply set the server name without pinging
      setState(prev => ({
        ...prev,
        serverId,
        loading: { ...prev.loading, server: false },
      }));

    } catch (error) {
      console.error('Error loading server:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to load server';
      toastError(`Failed to load server: ${errorMessage}`);
      setState(prev => ({
        ...prev,
        loading: { ...prev.loading, server: false },
        error: errorMessage,
      }));
    } finally {
      loadingRef.current.delete('server');
    }
  }, [isAuthenticated, user, toastError]);

  const loadTabData = useCallback(async (tab: 'tools' | 'resources' | 'prompts') => {
    if (!isAuthenticated || !user || !state.serverId) {
      return;
    }

    if (loadingRef.current.has(tab)) {
      return;
    }

    try {
      loadingRef.current.add(tab);
      setState(prev => ({
        ...prev,
        loading: { ...prev.loading, [tab]: true },
        error: null,
      }));

      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      let data: any[] = [];

      switch (tab) {
        case 'tools':
          const toolsResult = await apiClient.listMCPServerTools(state.serverId!, accessToken);
          if (!toolsResult.success) {
            throw new Error(toolsResult.error || 'Failed to load tools');
          }
          // Handle different response structures
          // Backend returns: { success, message, data: { server, tools: [...], total_tools } }
          const toolsData = Array.isArray(toolsResult.data) ? toolsResult.data : 
                           (toolsResult.data?.data?.tools || toolsResult.data?.tools || []);
          console.log('Tools data extracted:', toolsData);
          data = Array.isArray(toolsData) ? toolsData.map((tool: any) => ({
            name: tool.name,
            description: tool.description,
            inputSchema: tool.inputSchema || tool.parameters,
            server: state.serverId!,
          })) : [];
          break;

        case 'resources':
          const resourcesResult = await apiClient.listMCPServerResources(state.serverId!, accessToken);
          if (!resourcesResult.success) {
            throw new Error(resourcesResult.error || 'Failed to load resources');
          }
          // Handle different response structures
          // Backend returns: { success, message, data: { server, resources: [...], total_resources } }
          const resourcesData = Array.isArray(resourcesResult.data) ? resourcesResult.data : 
                               (resourcesResult.data?.data?.resources || resourcesResult.data?.resources || []);
          console.log('Resources data extracted:', resourcesData);
          data = Array.isArray(resourcesData) ? resourcesData.map((resource: any) => ({
            uri: resource.uri,
            name: resource.name,
            description: resource.description,
            server: state.serverId!,
          })) : [];
          break;

        case 'prompts':
          const promptsResult = await apiClient.listMCPServerPrompts(state.serverId!, accessToken);
          if (!promptsResult.success) {
            throw new Error(promptsResult.error || 'Failed to load prompts');
          }
          // Handle different response structures
          // Backend returns: { success, message, data: { server, prompts: [...], total_prompts } }
          const promptsData = Array.isArray(promptsResult.data) ? promptsResult.data : 
                             (promptsResult.data?.data?.prompts || promptsResult.data?.prompts || []);
          console.log('Raw prompts data:', promptsData);
          data = Array.isArray(promptsData) ? promptsData.map((prompt: any) => {
            const mappedPrompt = {
              name: prompt.name,
              description: prompt.description,
              arguments: prompt.arguments || prompt.args,
              server: state.serverId!,
            };
            console.log('Mapped prompt:', mappedPrompt);
            return mappedPrompt;
          }) : [];
          break;
      }

      setState(prev => ({
        ...prev,
        [tab]: data,
        loading: { ...prev.loading, [tab]: false },
        loadedTabs: new Set([...prev.loadedTabs, tab]),
      }));

    } catch (error) {
      console.error(`Error loading ${tab}:`, error);
      const errorMessage = error instanceof Error ? error.message : `Failed to load ${tab}`;
      toastError(`Failed to load ${tab}: ${errorMessage}`);
      setState(prev => ({
        ...prev,
        loading: { ...prev.loading, [tab]: false },
        error: errorMessage,
      }));
    } finally {
      loadingRef.current.delete(tab);
    }
  }, [isAuthenticated, user, state.serverId, toastError]);

  const testTool = useCallback(async (toolName: string, arguments_: Record<string, any>) => {
    if (!state.serverId) {
      throw new Error('No server selected');
    }

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const result = await apiClient.callMCPTool(state.serverId!, {
        tool_name: toolName,
        arguments: arguments_,
      }, accessToken);

      const testResult: TestResult = {
        success: result.success,
        result: result.data,
        error: result.error,
        timestamp: new Date().toISOString(),
      };

      setState(prev => ({
        ...prev,
        testResults: {
          ...prev.testResults,
          [`tool_${toolName}`]: testResult,
        },
      }));

    } catch (error) {
      const testResult: TestResult = {
        success: false,
        error: error instanceof Error ? error.message : 'Tool test failed',
        timestamp: new Date().toISOString(),
      };

      setState(prev => ({
        ...prev,
        testResults: {
          ...prev.testResults,
          [`tool_${toolName}`]: testResult,
        },
      }));
    }
  }, [state.serverId]);

  const testResource = useCallback(async (resourceUri: string) => {
    if (!state.serverId) {
      throw new Error('No server selected');
    }

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const result = await apiClient.getMCPResource(state.serverId!, {
        uri: resourceUri,
      }, accessToken);

      const testResult: TestResult = {
        success: result.success,
        result: result.data,
        error: result.error,
        timestamp: new Date().toISOString(),
      };

      setState(prev => ({
        ...prev,
        testResults: {
          ...prev.testResults,
          [`resource_${resourceUri}`]: testResult,
        },
      }));

    } catch (error) {
      const testResult: TestResult = {
        success: false,
        error: error instanceof Error ? error.message : 'Resource test failed',
        timestamp: new Date().toISOString(),
      };

      setState(prev => ({
        ...prev,
        testResults: {
          ...prev.testResults,
          [`resource_${resourceUri}`]: testResult,
        },
      }));
    }
  }, [state.serverId]);

  const testPrompt = useCallback(async (promptName: string, arguments_: Record<string, any>) => {
    if (!state.serverId) {
      throw new Error('No server selected');
    }

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const result = await apiClient.getMCPPrompt(state.serverId!, {
        prompt_name: promptName,
        arguments: arguments_,
      }, accessToken);

      const testResult: TestResult = {
        success: result.success,
        result: result.data,
        error: result.error,
        timestamp: new Date().toISOString(),
      };

      setState(prev => ({
        ...prev,
        testResults: {
          ...prev.testResults,
          [`prompt_${promptName}`]: testResult,
        },
      }));

    } catch (error) {
      const testResult: TestResult = {
        success: false,
        error: error instanceof Error ? error.message : 'Prompt test failed',
        timestamp: new Date().toISOString(),
      };

      setState(prev => ({
        ...prev,
        testResults: {
          ...prev.testResults,
          [`prompt_${promptName}`]: testResult,
        },
      }));
    }
  }, [state.serverId]);

  const clearTestResults = useCallback(() => {
    setState(prev => ({
      ...prev,
      testResults: {},
    }));
  }, []);

  const clearError = useCallback(() => {
    setState(prev => ({
      ...prev,
      error: null,
    }));
  }, []);

  const value: ServerTestContextType = {
    ...state,
    loadServer,
    loadTabData,
    testTool,
    testResource,
    testPrompt,
    clearTestResults,
    clearError,
  };

  return (
    <ServerTestContext.Provider value={value}>
      {children}
    </ServerTestContext.Provider>
  );
}

export function useServerTest() {
  const context = useContext(ServerTestContext);
  if (context === undefined) {
    throw new Error('useServerTest must be used within a ServerTestProvider');
  }
  return context;
} 