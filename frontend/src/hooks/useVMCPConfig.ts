// hooks/useVMCPConfig.ts
import { useState, useCallback, useEffect } from 'react';
import { VMCPConfig } from '../types/vmcp';
import { extractToolCalls } from '@/lib/vmcp';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

const LOCALSTORAGE_KEY_PREFIX = 'vmcp_draft_';

export const useVMCPConfig = (vmcpId: string, isNewVMCP: boolean) => {

  const [vmcpConfig, setVmcpConfig] = useState<VMCPConfig>({
    id: '',
    name: '',
    user_id: '',
    description: '',
    system_prompt: { text: '', variables: [], environment_variables: [], tool_calls: [] },
    vmcp_config: {
      name: '',
      description: '',
      enabled: true,
      selected_servers: [],
      selected_tools: {},
      selected_resources: {},
      selected_prompts: {},
      selected_tool_overrides: {},
      tags: [],
      is_default: false
    },
    custom_prompts: [],
    custom_tools: [],
    custom_context: [],
    custom_resources: [],
    custom_resource_templates: [],
    custom_resource_uris: [],
    environment_variables: [],
    uploaded_files: [],
    created_at: '',
    updated_at: '',
    created_by: '',
    total_tools: 0,
    total_resources: 0,
    total_resource_templates: 0,
    total_prompts: 0,
    is_public: false,
    public_info: {
      creator_id: '',
      creator_username: '',
      install_count: 0,
      rating: null,
      rating_count: 0
    },
    public_tags: [],
    public_at: '',
    is_wellknown: false,
    metadata: {}
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [originalConfig, setOriginalConfig] = useState<VMCPConfig | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [changesSummaryCache, setChangesSummaryCache] = useState<{
    updates: string[];
    additions: string[];
    deletions: string[]
  }>({ updates: [], additions: [], deletions: [] });

  // Memoized function to compute changes summary
  const computeChangesSummary = useCallback(() => {
    if (!originalConfig) return { updates: [], additions: [], deletions: [] };

    const updates: string[] = [];
    const additions: string[] = [];
    const deletions: string[] = [];

    console.log('🔍 Computing changes summary between original and current config');
    console.log('Original Config:', originalConfig);
    console.log('Current Config:', vmcpConfig);
    
    // Helper to get item identifiers
    const getItemName = (item: any): string => {
      return item?.name || item?.tool_name || item?.prompt_name || item?.resource_uri || item?.uri || item?.key || item?.id || 'Unknown';
    };

    // Helper to compare arrays and find differences
    const compareArrays = (category: string, oldArr: any[], newArr: any[], getKey: (item: any) => string) => {
      const oldKeys = new Set(oldArr.map(getKey));
      const newKeys = new Set(newArr.map(getKey));

      // Find additions
      newArr.forEach((item) => {
        const key = getKey(item);
        if (!oldKeys.has(key)) {
          additions.push(`${category}: ${key}`);
        } else {
          // Check for modifications
          const oldItem = oldArr.find((old) => getKey(old) === key);
          if (JSON.stringify(oldItem) !== JSON.stringify(item)) {
            updates.push(`${category}: ${key}`);
          }
        }
      });

      // Find deletions
      oldArr.forEach((item) => {
        const key = getKey(item);
        if (!newKeys.has(key)) {
          deletions.push(`${category}: ${key}`);
        }
      });
    };

    // Helper for object comparisons (tools, resources, prompts selections)
    const compareObjects = (category: string, oldObj: any, newObj: any) => {
      const oldKeys = new Set(Object.keys(oldObj || {}));
      const newKeys = new Set(Object.keys(newObj || {}));

      // Find additions and updates
      Object.keys(newObj || {}).forEach((serverName) => {
        const oldItems = oldObj?.[serverName] || [];
        const newItems = newObj?.[serverName] || [];

        if (!oldKeys.has(serverName)) {
          newItems.forEach((item: string) => additions.push(`${category} (${serverName}): ${item}`));
        } else {
          const oldSet = new Set(oldItems);
          const newSet = new Set(newItems);

          newItems.forEach((item: string) => {
            if (!oldSet.has(item)) additions.push(`${category} (${serverName}): ${item}`);
          });

          oldItems.forEach((item: string) => {
            if (!newSet.has(item)) deletions.push(`${category} (${serverName}): ${item}`);
          });
        }
      });

      // Find deletions (entire server removed)
      Object.keys(oldObj || {}).forEach((serverName) => {
        if (!newKeys.has(serverName)) {
          (oldObj[serverName] || []).forEach((item: string) =>
            deletions.push(`${category} (${serverName}): ${item}`)
          );
        }
      });
    };

    // Helper for nested object comparisons (tool overrides)
    const compareNestedObjects = (category: string, oldObj: any, newObj: any) => {
      const oldKeys = new Set(Object.keys(oldObj || {}));
      const newKeys = new Set(Object.keys(newObj || {}));

      // Check each server
      Object.keys(newObj || {}).forEach((serverId) => {
        const oldServerOverrides = oldObj?.[serverId] || {};
        const newServerOverrides = newObj?.[serverId] || {};

        // Check each tool override within this server
        Object.keys(newServerOverrides).forEach((toolName) => {
          const oldOverride = oldServerOverrides[toolName];
          const newOverride = newServerOverrides[toolName];

          if (!oldOverride) {
            additions.push(`${category} (${serverId}): ${toolName}`);
          } else if (JSON.stringify(oldOverride) !== JSON.stringify(newOverride)) {
            updates.push(`${category} (${serverId}): ${toolName}`);
          }
        });

        // Check for deletions within this server
        Object.keys(oldServerOverrides).forEach((toolName) => {
          if (!newServerOverrides[toolName]) {
            deletions.push(`${category} (${serverId}): ${toolName}`);
          }
        });
      });

      // Check for entirely deleted servers
      Object.keys(oldObj || {}).forEach((serverId) => {
        if (!newKeys.has(serverId)) {
          const oldServerOverrides = oldObj[serverId] || {};
          Object.keys(oldServerOverrides).forEach((toolName) => {
            deletions.push(`${category} (${serverId}): ${toolName}`);
          });
        }
      });
    };

    // Check top-level fields
    if (originalConfig.name !== vmcpConfig.name) {
      updates.push(`Name: "${originalConfig.name}" → "${vmcpConfig.name}"`);
    }
    if (originalConfig.description !== vmcpConfig.description) {
      updates.push(`Description: "${originalConfig.description}" → "${vmcpConfig.description}"`);
    }

    // Check system prompt
    if (JSON.stringify(originalConfig.system_prompt) !== JSON.stringify(vmcpConfig.system_prompt)) {
      updates.push(`System Prompt: "${JSON.stringify(originalConfig.system_prompt)}" → "${JSON.stringify(vmcpConfig.system_prompt)}"`);
    }

    // // Check selected servers
    // compareArrays(
    //   'MCP Server',
    //   originalConfig.vmcp_config.selected_servers || [],
    //   vmcpConfig.vmcp_config.selected_servers || [],
    //   (item) => item.name || item.server_name
    // );

    // Check selected tools, resources, prompts
    compareObjects('Tool', originalConfig.vmcp_config.selected_tools, vmcpConfig.vmcp_config.selected_tools);
    compareObjects('Resource', originalConfig.vmcp_config.selected_resources, vmcpConfig.vmcp_config.selected_resources);
    compareObjects('Prompt', originalConfig.vmcp_config.selected_prompts, vmcpConfig.vmcp_config.selected_prompts);

    // Check tool overrides (nested object structure)
    compareNestedObjects(
      'Tool Override',
      (originalConfig.vmcp_config as any).selected_tool_overrides,
      (vmcpConfig.vmcp_config as any).selected_tool_overrides
    );

    // Check custom prompts
    compareArrays(
      'Custom Prompt',
      originalConfig.custom_prompts || [],
      vmcpConfig.custom_prompts || [],
      getItemName
    );

    // Check custom tools
    compareArrays(
      'Custom Tool',
      originalConfig.custom_tools || [],
      vmcpConfig.custom_tools || [],
      getItemName
    );

    // Check custom resources
    compareArrays(
      'Custom Resource',
      originalConfig.custom_resources || [],
      vmcpConfig.custom_resources || [],
      getItemName
    );

    // Check config variables
    compareArrays(
      'Config Variable',
      originalConfig.environment_variables || [],
      vmcpConfig.environment_variables || [],
      (item) => item.name || item.key
    );

    // Check uploaded files
    compareArrays(
      'File',
      originalConfig.uploaded_files || [],
      vmcpConfig.uploaded_files || [],
      (item) => item.filename || item.original_filename
    );


    // Check metadata
    if (JSON.stringify(originalConfig.metadata) !== JSON.stringify(vmcpConfig.metadata)) {
      const oldKeys = Object.keys(originalConfig.metadata || {});
      const newKeys = Object.keys(vmcpConfig.metadata || {});

      newKeys.forEach(key => {
        const newVal = vmcpConfig.metadata?.[key];

        if (!oldKeys.includes(key)) {
          if(newVal !== null && newVal !== undefined && newVal !== '') {
            additions.push(`Metadata: ${key}`);
          }
        } else if (originalConfig.metadata?.[key] !== vmcpConfig.metadata?.[key]) {
          updates.push(`Metadata: ${key}`);
        }
      });

      oldKeys.forEach(key => {
        if (!newKeys.includes(key)) {
          const oldVal = originalConfig.metadata?.[key];
          if(oldVal !== null && oldVal !== undefined && oldVal !== '') {
            deletions.push(`Metadata: ${key}`);
          }
        }
      });
    }

    return { updates, additions, deletions };
  }, [originalConfig, vmcpConfig]);

  // Reset state when vmcpId changes to prevent data persistence between different VMCPS
  useEffect(() => {
    console.log(`🔄 VMCP ID changed to: ${vmcpId}`);
    // Reset comparison state when vmcpId changes, but don't reset vmcpConfig
    // The vmcpConfig will be loaded by loadVMCPConfig
    setOriginalConfig(null);
    setHasUnsavedChanges(false);
    setChangesSummaryCache({ updates: [], additions: [], deletions: [] });
  }, [vmcpId]);

  // Save current config to localStorage and compute changes whenever config changes
  useEffect(() => {
    if(!vmcpConfig.is_public) {
      if (vmcpId && vmcpConfig.id) {
        const storageKey = `${LOCALSTORAGE_KEY_PREFIX}${vmcpId}`;
        localStorage.setItem(storageKey, JSON.stringify(vmcpConfig));

        // Compute changes summary
        if (originalConfig) {
          const summary = computeChangesSummary();
          setChangesSummaryCache(summary);

          // Check if there are any changes
          const hasChanges = summary.updates.length > 0 || summary.additions.length > 0 || summary.deletions.length > 0;
          setHasUnsavedChanges(hasChanges);
        }
      }
    }
  }, [vmcpConfig, vmcpId, originalConfig, computeChangesSummary]);

  const loadVMCPConfig = useCallback(async () => {
    if (isNewVMCP) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        console.error('No access token available');
        setLoading(false);
        return;
      }

      // Check for localStorage draft first
      const storageKey = `${LOCALSTORAGE_KEY_PREFIX}${vmcpId}`;
      const localDraft = localStorage.getItem(storageKey);

      console.log(`🔄 Fetching complete VMCPConfig for vMCP ID: ${vmcpId}`);
      const result = await apiClient.getVMCPDetails(vmcpId, accessToken);

      if (result.success && result.data) {
        const data = result.data as any;

        // Map the backend data to VMCPConfig format
        const mappedConfig: VMCPConfig = {
          id: data.id || data.vmcp_id || data.public_vmcp_id,
          name: data.vmcp_registry_config?.name || data.name || '',
          user_id: data.user_id || '',
          description: data.vmcp_registry_config?.description || data.description || '',
          system_prompt: (data as any).system_prompt ? {
            ...(data as any).system_prompt,
            environment_variables: (data as any).system_prompt.environment_variables || [],
            tool_calls: (data as any).system_prompt.tool_calls || []
          } : { text: '', variables: [], environment_variables: [], tool_calls: [] },
          vmcp_config: data.vmcp_config || {
            name: '',
            description: '',
            enabled: true,
            selected_servers: [],
            selected_tools: {},
            selected_resources: {},
            selected_prompts: {},
            selected_tool_overrides: {},
            tags: [],
            is_default: false
          },
          custom_prompts: ((data as any).custom_prompts || []).map((prompt: any) => ({
            ...prompt,
            environment_variables: prompt.environment_variables || [],
            tool_calls: prompt.tool_calls || []
          })),
          custom_tools: Array.isArray((data as any).custom_tools) ? (data as any).custom_tools.map((tool: any) => ({
            ...tool,
            tool_calls: tool.tool_calls || []
          })) : [],
          custom_context: (data as any).custom_context || [],
          custom_resources: (data as any).custom_resources || [],
          custom_resource_templates: (data as any).custom_resource_templates || [],
          custom_resource_uris: (data as any).custom_resource_uris || [],
          environment_variables: (data as any).environment_variables || [],
          uploaded_files: (data as any).uploaded_files || [],
          created_at: data.created_at || '',
          updated_at: data.updated_at || '',
          created_by: (data as any).created_by || '',
          total_tools: (data as any).total_tools || 0,
          total_resources: (data as any).total_resources || 0,
          total_resource_templates: (data as any).total_resource_templates || 0,
          total_prompts: (data as any).total_prompts || 0,
          is_public: data.is_public || false,
          public_info: (data as any).public_info || {
            creator_id: '',
            creator_username: '',
            install_count: 0,
            rating: null,
            rating_count: 0
          },
          public_tags: data.public_tags || [],
          public_at: data.public_at || '',
          is_wellknown: (data as any).is_wellknown || false,
          metadata: (data as any).metadata || {}
        };

        // Store original config for comparison
        setOriginalConfig(mappedConfig);

        // Always load fresh data from backend when switching VMCPS
        // Only use localStorage draft if it's for the same VMCP and we're not switching
        console.log('📦 Loading vMCP config from backend data');
        setVmcpConfig(mappedConfig);
        setHasUnsavedChanges(false);
        
        // Check if there's a draft for this VMCP and show unsaved changes if different
        if (localDraft) {
          try {
            const draftConfig = JSON.parse(localDraft);
            const hasChanges = JSON.stringify(draftConfig) !== JSON.stringify(mappedConfig);
            if (hasChanges) {
              console.log('📝 Found unsaved changes in localStorage draft');
              setHasUnsavedChanges(true);
            }
          } catch (e) {
            console.error('Failed to parse localStorage draft:', e);
          }
        }

        console.log('✅ Successfully loaded complete VMCPConfig from backend:', mappedConfig);
      } else {
        console.error('Failed to load vMCP config:', result.error);
      }
    } catch (error) {
      console.error('Error loading vMCP config:', error);
    } finally {
      setLoading(false);
    }
  }, [vmcpId, isNewVMCP]);

  const clearLocalStorage = useCallback(() => {
    if (vmcpId) {
      const storageKey = `${LOCALSTORAGE_KEY_PREFIX}${vmcpId}`;
      localStorage.removeItem(storageKey);
      setHasUnsavedChanges(false);
      setChangesSummaryCache({ updates: [], additions: [], deletions: [] });
    }
  }, [vmcpId]);

  // Return cached changes summary - no need to recompute
  const getChangesSummary = useCallback(() => {
    return changesSummaryCache;
  }, [changesSummaryCache]);

  return {
    vmcpConfig,
    setVmcpConfig,
    loading,
    setLoading,
    saving,
    setSaving,
    loadVMCPConfig,
    hasUnsavedChanges,
    setHasUnsavedChanges,
    originalConfig,
    clearLocalStorage,
    getChangesSummary,
  };
};