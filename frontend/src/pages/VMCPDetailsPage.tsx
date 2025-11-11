
import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { Settings, Save, Trash2, Edit2, Check, X, Globe, GitFork, Copy, ExternalLink, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/contexts/auth-context';
import { useVMCP, useVMCPById } from '@/contexts/vmcp-context';
import { useServers } from '@/contexts/servers-context';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';
import { ConfirmationDialog } from '@/components/ui/confirmation-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';

// Import types and utilities
import { extractToolCalls } from '@/lib/vmcp';
import { useVMCPConfig } from '@/hooks/useVMCPConfig';

// Import tab components
import SystemTab from '@/components/vmcp/SystemTab';
import MCPServersTab from '@/components/vmcp/MCPServersTab';
import PromptsTab from '@/components/vmcp/PromptsTab';
import ToolsTab from '@/components/vmcp/ToolsTab';
import ResourcesTab from '@/components/vmcp/ResourcesTab';
import EnvironmentVariablesTab from '@/components/vmcp/EnvironmentVariablesTab';

export default function VMCPDetailPage() {
  const params = useParams();
  const router = useRouter();
  const vmcpId = params.id as string;
  const isNewVMCP = vmcpId === 'new';

  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const { forceRefreshVMCPData, vmcps } = useVMCP();
  const { servers, loading: serversLoading } = useServers();
  const { success: showSuccess, error: showError } = useToast();

  // Use the custom hook for VMCP config management
  const {
    vmcpConfig,
    setVmcpConfig,
    loading,
    setLoading,
    saving,
    setSaving,
    loadVMCPConfig,
    hasUnsavedChanges,
    setHasUnsavedChanges,
    clearLocalStorage,
    getChangesSummary,
  } = useVMCPConfig(vmcpId, isNewVMCP);

  // Local state for UI management
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['mcp_servers']));
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [renamingFile, setRenamingFile] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState('');
  const [forking, setForking] = useState(false);
  const [urlCopied, setUrlCopied] = useState(false);
  const [showExtendDialog, setShowExtendDialog] = useState(false);
  const [extendName, setExtendName] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  // Header editing state (now in modal)
  const [showEditHeaderModal, setShowEditHeaderModal] = useState(false);
  const [editingName, setEditingName] = useState('');
  const [editingDescription, setEditingDescription] = useState('');
  const [editingMetadata, setEditingMetadata] = useState<Array<{key: string, value: string}>>([]);

  // Changes summary dialog state
  const [showChangesSummaryDialog, setShowChangesSummaryDialog] = useState(false);
  const [showDiscardConfirmDialog, setShowDiscardConfirmDialog] = useState(false);
  
  // Check if vMCP has a name to determine display
  const hasVMCPName = vmcpConfig.name && vmcpConfig.name.trim() !== '';

  // Compute changes summary for the dialog
  const changesSummary = getChangesSummary();
  const hasChanges = changesSummary.updates.length > 0 || changesSummary.additions.length > 0 || changesSummary.deletions.length > 0;
  
  // Check if this is a remote vMCP (from the public vMCPs tab)
  const decodedVmcpId = decodeURIComponent(vmcpId);
  const isRemoteVMCP = vmcps.public && vmcps.public.some(vmcp => {
    const matches = vmcp.id === decodedVmcpId;
    console.log(`🔍 Comparing vMCP IDs: "${vmcp.id}" === "${decodedVmcpId}" = ${matches}`);
    return matches;
  });
  
  // Debug logging
  console.log('🔍 Remote vMCP Debug Info:', {
    vmcpId,
    decodedVmcpId,
    vmcpsPublicCount: vmcps.public?.length || 0,
    vmcpsPublicIds: vmcps.public?.map(vmcp => vmcp.id),
    isRemoteVMCP,
    vmcpConfigName: vmcpConfig.name,
    vmcpConfigId: vmcpConfig.id,
    vmcpsPrivateCount: vmcps.private?.length || 0,
    vmcpsPrivateIds: vmcps.private?.map(vmcp => vmcp.id)
  });

  // Function to get VMCP URL from metadata
  const getVMCPUrl = useCallback(() => {
    console.log('vmcpConfig metadata', vmcpConfig.metadata);
    return vmcpConfig.metadata?.url || '';
  }, [vmcpConfig.metadata?.url]);

  // Function to copy VMCP URL to clipboard
  const handleCopyUrl = async () => {
    const url = getVMCPUrl();
    if (!url) return;
    
    try {
      await navigator.clipboard.writeText(url);
      setUrlCopied(true);
      // Reset copied state after 2 seconds
      setTimeout(() => setUrlCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy URL:', error);
      showError('Failed to copy URL to clipboard');
    }
  };

  // Server selection state - removed unused local state variables
  // The selections are now managed directly in vmcpConfig.vmcp_config

  // Server-specific data loading
  const [serverSpecificData, setServerSpecificData] = useState<{
    [serverName: string]: {
      tools: any[];
      prompts: any[];
      resources: any[];
    }
  }>({});

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
      return;
    }
  }, [authLoading, isAuthenticated, router]);

  // Reset state when vmcpId changes to prevent data persistence between different VMCPS
  useEffect(() => {
    setServerSpecificData({});
    setExpandedSections(new Set(['mcp_servers']));
    setShowDeleteModal(false);
    setShowEditHeaderModal(false);
    setShowExtendDialog(false);
    setShowChangesSummaryDialog(false);
    setShowDiscardConfirmDialog(false);
    setEditingName('');
    setEditingDescription('');
    setEditingMetadata([]);
    setExtendName('');
    setUrlCopied(false);
  }, [vmcpId]);

  useEffect(() => {
    console.log(`🔄 VMCPDetailsPage: vmcpId changed to ${vmcpId}, isNewVMCP: ${isNewVMCP}`);
    if (isNewVMCP) {
      // Component is already initialized with empty config
      setLoading(false);
    } else {
      console.log(`📥 Loading VMCP config for ID: ${vmcpId}`);
      loadVMCPConfig();
    }
  }, [vmcpId, isNewVMCP, loadVMCPConfig]);

  // Server selections are now managed directly in vmcpConfig.vmcp_config
  // No need for separate state initialization

  // Function to get all tools from all selected servers
  const getAllTools = useCallback(() => {
    const allTools: any[] = [];
    vmcpConfig.vmcp_config.selected_servers?.forEach(server => {
      const serverData = serverSpecificData[server.name];
      if (serverData && serverData.tools && serverData.tools.length > 0) {
        const toolsWithServer = serverData.tools.map((tool: any) => ({
          ...tool,
          server: server.name
        }));
        allTools.push(...toolsWithServer);
      }
    });
    return allTools;
  }, [vmcpConfig.vmcp_config.selected_servers, serverSpecificData]);

  // Function to get all resources from all selected servers
  const getAllResources = useCallback(() => {
    const allResources: any[] = [];
    vmcpConfig.vmcp_config.selected_servers?.forEach(server => {
      const serverData = serverSpecificData[server.name];
      if (serverData && serverData.resources && serverData.resources.length > 0) {
        allResources.push(...serverData.resources);
      }
    });
    return allResources;
  }, [vmcpConfig.vmcp_config.selected_servers, serverSpecificData]);

  const handleSaveClick = () => {
    if (!vmcpConfig.name.trim()) {
      showError('vMCP name is required');
      return;
    }

    if (!vmcpConfig.system_prompt.text.trim()) {
      showError('System prompt is required');
      return;
    }

    // Show changes summary dialog
    setShowChangesSummaryDialog(true);
  };

  const handleDiscardDraft = () => {
    setShowDiscardConfirmDialog(true);
  };

  const confirmDiscardDraft = () => {
    clearLocalStorage();
    loadVMCPConfig();
    setShowChangesSummaryDialog(false);
    setShowDiscardConfirmDialog(false);
    showSuccess('Changes discarded successfully');
  };

  const handleSave = async () => {
    setShowChangesSummaryDialog(false);
    setSaving(true);
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      if (!accessToken) {
        showError('No access token available');
        return;
      }

      // Re-extract tool calls from all prompts before saving
      const updatedCustomPrompts = vmcpConfig.custom_prompts.map(prompt => ({
        ...prompt,
        tool_calls: extractToolCalls(prompt.text, getAllTools())
      }));

      const updatedCustomTools = vmcpConfig.custom_tools.map(tool => ({
        ...tool,
        tool_calls: extractToolCalls(tool.text, getAllTools())
      }));

      const updatedSystemPrompt = {
        ...vmcpConfig.system_prompt,
        tool_calls: extractToolCalls(vmcpConfig.system_prompt.text, getAllTools())
      };

      // Prepare the data with selected tools, prompts, and resources
      const saveData = {
        name: vmcpConfig.name,
        description: vmcpConfig.description,
        system_prompt: updatedSystemPrompt,
        vmcp_config: {
          ...vmcpConfig.vmcp_config,
          // Use the data directly from vmcpConfig instead of local state variables
          selected_tools: vmcpConfig.vmcp_config.selected_tools,
          selected_prompts: vmcpConfig.vmcp_config.selected_prompts,
          selected_resources: vmcpConfig.vmcp_config.selected_resources
        },
        custom_prompts: updatedCustomPrompts,
        custom_tools: updatedCustomTools,
        custom_context: vmcpConfig.custom_context,
        custom_resources: vmcpConfig.custom_resources,
        custom_resource_uris: vmcpConfig.custom_resource_uris,
        environment_variables: vmcpConfig.environment_variables,
        uploaded_files: vmcpConfig.uploaded_files,
        metadata: vmcpConfig.metadata
      };

      let result;
      if (isNewVMCP) {
        result = await apiClient.createVMCP(saveData as any, accessToken);
      } else {
        result = await apiClient.updateVMCP(vmcpId, saveData as any, accessToken);
      }

      if (result.success) {
        showSuccess('vMCP saved successfully!');
        clearLocalStorage(); // Clear the draft after successful save
        loadVMCPConfig();
        forceRefreshVMCPData();
        if (isNewVMCP && result.data?.id) {
          router.push(`/vmcp/${result.data.id}`);
        }
      } else {
        console.error('Save failed:', result.error);
        showError('Failed to save vMCP');
      }
    } catch (error) {
      console.error('Error saving vMCP:', error);
      showError('Error saving vMCP');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (isNewVMCP) return;

    setDeleting(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        showError('No access token available');
        return;
      }

      const result = await apiClient.deleteVMCP(vmcpId, accessToken);

      if (result.success) {
        showSuccess('vMCP deleted successfully');
        forceRefreshVMCPData();
        router.push('/vmcp');
      } else {
        showError('Failed to delete vMCP');
      }
    } catch (error) {
      console.error('Error deleting vMCP:', error);
      showError('Error deleting vMCP');
    } finally {
      setDeleting(false);
      setShowDeleteModal(false);
    }
  };

  const handleFork = async () => {
    if (!isRemoteVMCP) return;

    setForking(true);
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      if (!accessToken) {
        showError('No access token available');
        return;
      }

      const result = await apiClient.createVMCP({
        ...vmcpConfig,
        name: `${vmcpConfig.name}-forked-${Date.now()}`
      } as any, accessToken);

      if (result.success) {
        const forkedName = result.data?.name || 'Forked vMCP';
        showSuccess(`vMCP forked successfully as "${forkedName}"! You can now edit your private copy.`);
        forceRefreshVMCPData();
        if (result.data?.id) {
          router.push(`/vmcp/${result.data.id}`);
        }
      } else {
        console.error('Fork failed:', result.error);
        showError(`Failed to fork vMCP: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error forking vMCP:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showError(`Error forking vMCP: ${errorMessage}`);
    } finally {
      setForking(false);
    }
  };

  const handleExtendClick = () => {
    // Set default name to the part after "/" for public vMCPs
    const defaultName = vmcpConfig.name.includes('/') 
      ? vmcpConfig.name.split('/').slice(1).join('/')
      : vmcpConfig.name;
    setExtendName(defaultName);
    setShowExtendDialog(true);
  };

  const handleExtendConfirm = async () => {
    if (!extendName.trim()) {
      showError('Please enter a name for your private copy');
      return;
    }

    setForking(true);
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      if (!accessToken) {
        showError('No access token available');
        return;
      }

      // Create a copy of the current vMCP config with the new name and ID
      const newName = extendName.trim();
      const extendedConfig = {
        ...vmcpConfig,
        id: newName, // Update the ID to match the new name
        name: newName,
        // Remove any public-specific fields to make it private
        is_public: false,
        public_tags: [],
        public_at: null
      };

      const result = await apiClient.createVMCP(extendedConfig as any, accessToken);

      if (result.success) {
        const extendedName = result.data?.name || newName;
        const newVmcpId = result.data?.id;
        showSuccess(`vMCP extended successfully as "${extendedName}"! You can now edit your private copy.`);
        forceRefreshVMCPData();
        // Navigate to the new vMCP using the returned vmcp_id
        if (newVmcpId) {
          router.push(`/vmcp/${encodeURIComponent(newVmcpId)}`);
        }
      } else {
        console.error('Extend failed:', result.error);
        showError(`Failed to extend vMCP: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error extending vMCP:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showError(`Error extending vMCP: ${errorMessage}`);
    } finally {
      setForking(false);
      setShowExtendDialog(false);
      setExtendName('');
    }
  };

  const handleExtendCancel = () => {
    setShowExtendDialog(false);
    setExtendName('');
  };

  const handleRefresh = async () => {
    if (isNewVMCP) return;

    setRefreshing(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        showError('No access token available');
        setRefreshing(false);
        return;
      }

      const result = await apiClient.refreshVMCP(vmcpId, accessToken);
      
      if (result.success) {
        showSuccess('vMCP refreshed successfully');
        // Reload the vMCP config to reflect the refreshed state
        await loadVMCPConfig();
        forceRefreshVMCPData();
      } else {
        showError(result.error || 'Failed to refresh vMCP');
      }
    } catch (error) {
      console.error('Error refreshing vMCP:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showError(`Error refreshing vMCP: ${errorMessage}`);
    } finally {
      setRefreshing(false);
    }
  };

  // File upload handlers
  const handleFileUpload = async (files: FileList) => {
    const uploadedFiles = Array.from(files);
    setUploadingFiles(true);

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        console.error('No access token available');
        return;
      }

      for (const file of uploadedFiles) {
        const result = await apiClient.uploadBlob(file, accessToken, vmcpConfig.id);

        if (result.success && result.data) {
          const newFile = {
            id: result.data.blob_id,
            url: result.data.url,
            original_filename: file.name,
            filename: result.data.normalized_name || file.name,
            resource_name: result.data.resource_name || file.name,
            content_type: result.data.content_type || file.type || 'application/octet-stream',
            size: result.data.size || file.size,
            vmcp_id: vmcpConfig.id,
            user_id: result.data.user_id,
            created_at: result.data.created_at || new Date().toISOString()
          };
          
          setVmcpConfig(prev => ({
            ...prev,
            uploaded_files: [...prev.uploaded_files, newFile],
            custom_resources: [...prev.custom_resources, newFile]
          }));
        }
      }
    } catch (error) {
      console.error('Error uploading file:', error);
    } finally {
      setUploadingFiles(false);
    }
  };

  const handleFileRemove = async (blobId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        console.error('No access token available');
        return;
      }

      const result = await apiClient.deleteBlob(blobId, accessToken, vmcpConfig.id);

      if (result.success) {
        setVmcpConfig(prev => ({
          ...prev,
          uploaded_files: prev.uploaded_files.filter(f => f.id !== blobId),
          custom_resources: prev.custom_resources.filter(f => f.id !== blobId)
        }));
      }
    } catch (error) {
      console.error('Error removing file:', error);
    }
  };

  const handleFileRename = async (blobId: string, newFilename: string) => {
    try {
      setRenamingFile(blobId);
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        console.error('No access token available');
        return;
      }

      const result = await apiClient.renameBlob(blobId, newFilename, accessToken, vmcpConfig.id);
      console.log('vmcpId', vmcpConfig.id);
      if (result.success && result.data) {
        console.log('result.data', result.data);
        const updatedFile = { original_filename: result.data.original_name, 
          original_name: result.data.original_name,
          filename: result.data.filename,
          resource_name: result.data.resource_name
        };
        setVmcpConfig(prev => ({
          ...prev,
          uploaded_files: prev.uploaded_files.map(f =>
            f.id === blobId ? { ...f, ...updatedFile } : f
          ),
          custom_resources: prev.custom_resources.map(f =>
            f.id === blobId ? { ...f, ...updatedFile } : f
          )
        }));
        setRenamingFile(null);
        setNewFileName('');
      }
    } catch (error) {
      console.error('Error renaming file:', error);
    } finally {
      setRenamingFile(null);
    }
  };

  // Environment variable management
  const addEnvironmentVariable = () => {
    setVmcpConfig(prev => ({
      ...prev,
      environment_variables: [...prev.environment_variables, { 
        name: '', 
        value: '', 
        description: '', 
        required: false, 
        source: 'manual' 
      }]
    }));
  };

  const removeEnvironmentVariable = (index: number) => {
    setVmcpConfig(prev => ({
      ...prev,
      environment_variables: prev.environment_variables.filter((_, i) => i !== index)
    }));
  };

  const updateEnvironmentVariable = (index: number, field: 'name' | 'value' | 'description' | 'required' | 'source', value: string | boolean) => {
    setVmcpConfig(prev => ({
      ...prev,
      environment_variables: prev.environment_variables.map((env, i) =>
        i === index ? { ...env, [field]: value } : env
      )
    }));
  };

  // Header editing functions
  const startEditingHeader = () => {
    setEditingName(vmcpConfig.name);
    setEditingDescription(vmcpConfig.description);

    // Initialize metadata with only icon and author keys
    const currentMetadata = vmcpConfig.metadata || {};
    const defaultKeys = ['icon', 'author']; // Only icon and author
    const metadataArray = defaultKeys.map(key => ({
      key,
      value: currentMetadata[key] || ''
    }));

    setEditingMetadata(metadataArray);
    setShowEditHeaderModal(true);
  };

  const cancelEditingHeader = () => {
    setEditingName('');
    setEditingDescription('');
    setEditingMetadata([]);
    setShowEditHeaderModal(false);
  };

  const saveHeaderEdit = () => {
    if (!editingName.trim()) {
      showError('vMCP name is required');
      return;
    }

    // Convert metadata array to object, preserving existing metadata
    const editedMetadata = editingMetadata.reduce((acc, item) => {
      if (item.key.trim()) {
        acc[item.key.trim()] = item.value.trim();
      }
      return acc;
    }, {} as Record<string, string>);

    // Merge edited metadata with existing metadata to preserve other fields
    const mergedMetadata = {
      ...vmcpConfig.metadata, // Preserve existing metadata
      ...editedMetadata // Override with edited fields
    };

    setVmcpConfig(prev => ({
      ...prev,
      name: editingName.trim(),
      description: editingDescription.trim(),
      metadata: mergedMetadata
    }));
    setShowEditHeaderModal(false);
  };

  // Metadata management functions
  // Comment out addMetadataField - only allow icon and author
  // const addMetadataField = () => {
  //   setEditingMetadata(prev => [...prev, { key: '', value: '' }]);
  // };

  const removeMetadataField = (index: number) => {
    setEditingMetadata(prev => prev.filter((_, i) => i !== index));
  };

  const updateMetadataField = (index: number, field: 'key' | 'value', value: string) => {
    setEditingMetadata(prev => prev.map((item, i) => 
      i === index ? { ...item, [field]: value } : item
    ));
  };

  // Function to get icon display
  const getIconDisplay = (iconValue: string) => {
    if (!iconValue) return null;
    
    if (iconValue.startsWith('data:image/') || iconValue.startsWith('data:image/png') || iconValue.startsWith('data:image/jpeg')) {
      return <img src={iconValue} alt="Icon" className="h-6 w-6 rounded object-cover" />;
    } else if (iconValue.startsWith('http')) {
      return <img src={iconValue} alt="Icon" className="h-6 w-6 rounded object-cover" />;
    }
    return <span className="text-xs text-muted-foreground truncate max-w-20">{iconValue}</span>;
  };

  // Custom prompt management
  const addCustomPrompt = () => {
    setVmcpConfig(prev => ({
      ...prev,
      custom_prompts: [...prev.custom_prompts, {
        name: '',
        description: '',
        text: '',
        variables: [],
        environment_variables: [],
        tool_calls: []
      }]
    }));
  };

  const removeCustomPrompt = (index: number) => {
    setVmcpConfig(prev => ({
      ...prev,
      custom_prompts: prev.custom_prompts.filter((_, i) => i !== index)
    }));
  };

  // Custom tool management
  const addCustomTool = (toolType: 'prompt' | 'python' | 'http' = 'prompt') => {
    const baseTool = {
      name: '',
      description: '',
      text: '',
      variables: [],
      environment_variables: [],
      tool_calls: []
    };

    // Add tool type specific properties
    const toolWithType = {
      ...baseTool,
      tool_type: toolType,
      // For Python tools, add code field
      ...(toolType === 'python' && { 
        code: '',
        imports: [],
        dependencies: []
      }),
      // For HTTP tools, add API configuration
      ...(toolType === 'http' && { 
        api_config: {
          method: 'GET',
          url: '',
          headers: {},
          body: null,
          query_params: {}
        },
        imported_from: null // 'postman' | 'openapi' | null
      })
    };

    setVmcpConfig(prev => ({
      ...prev,
      custom_tools: [...prev.custom_tools, toolWithType]
    }));
  };

  const removeCustomTool = (index: number) => {
    setVmcpConfig(prev => ({
      ...prev,
      custom_tools: prev.custom_tools.filter((_, i) => i !== index)
    }));
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading vMCP...</p>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen text-foreground">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1">
            <div className="h-12 w-12 rounded-xl bg-primary/20 flex items-center justify-center overflow-hidden">
              {vmcpConfig.metadata?.icon ? (
                <img 
                  src={vmcpConfig.metadata.icon.startsWith('data:') 
                    ? vmcpConfig.metadata.icon 
                    : vmcpConfig.metadata.icon.startsWith('http') 
                      ? vmcpConfig.metadata.icon 
                      : `data:image/png;base64,${vmcpConfig.metadata.icon}`} 
                  alt="VMCP Icon"
                  className="h-8 w-8 object-contain"
                  onError={(e) => {
                    // Fallback to settings icon if image fails to load
                    e.currentTarget.style.display = 'none';
                    e.currentTarget.nextElementSibling?.classList.remove('hidden');
                  }}
                />
              ) : null}
              <Settings className={`h-8 w-8 text-primary ${vmcpConfig.metadata?.icon ? 'hidden' : ''}`} />
            </div>
            <div className="flex-1">
              <div>
                <div className="flex items-center gap-2">
                  {hasVMCPName ? (
                    vmcpConfig.is_public ? (
                      <h1 className="text-3xl font-bold text-foreground">
                        vMCP: <span className=" text-primary">{vmcpConfig.name.split('/')[0]}/</span>{vmcpConfig.name.split('/').slice(1).join('/')}
                      </h1>
                    ) : (
                      <h1 className="text-3xl font-bold text-foreground">
                        Edit vMCP: {vmcpConfig.name}
                      </h1>
                    )
                  ) : (
                    <h1 className="text-3xl font-bold text-foreground">
                      Create New vMCP
                    </h1>
                  )}
                  {!isRemoteVMCP && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={startEditingHeader}
                      className="h-8 w-8 p-0 opacity-60 hover:opacity-100"
                    >
                      <Edit2 className="h-4 w-4 bg-pr" />
                    </Button>
                  )}
                </div>
                <p className="text-muted-foreground">
                  {vmcpConfig.description || 'Configure your virtual Model Context Protocol agent'}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {!isNewVMCP && (
              <>
                <Button
                  variant="outline"
                  onClick={handleRefresh}
                  disabled={refreshing}
                  className="hover:text-primary"
                >
                  {refreshing ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent mr-2"></div>
                      Refreshing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Refresh
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowDeleteModal(true)}
                  className="hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </>
            )}
            <Button
              onClick={isRemoteVMCP ? handleExtendClick : handleSaveClick}
              disabled={saving || (isRemoteVMCP && forking) || (!isRemoteVMCP && !hasUnsavedChanges)}
              title={isRemoteVMCP ? 'Create a private copy to extend this vMCP' : hasUnsavedChanges ? 'Save changes' : 'No changes to save'}
            >
              {saving || forking ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent mr-2"></div>
                  {isRemoteVMCP ? 'Extending...' : 'Saving...'}
                </>
              ) : (
                <>
                  {isRemoteVMCP ? (
                    <>
                      <GitFork className="h-4 w-4 mr-2" />
                      Extend vMCP
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save vMCP
                    </>
                  )}
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Remote vMCP Banner */}
      {isRemoteVMCP && (
        <div className="mb-2 border border-accent/50 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <Globe className="h-5 w-5 text-accent mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground mt-1">
                  This is a community vMCP. You can only authenticate with MCP servers. All other configuration is read-only.
                </p>
                <p className="text-xs">
                  Want to make changes? Extend this vMCP to create your own private copy.
                </p>
              </div>
            </div>
            {/* <Button
              onClick={handleFork}
              disabled={forking}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {forking ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2"></div>
                  Forking...
                </>
              ) : (
                <>
                  <GitFork className="h-4 w-4 mr-2" />
                  Fork vMCP
                </>
              )}
            </Button> */}
          </div>
        </div>
      )}

      {/* Tabs implementation */}
      <Tabs defaultValue="mcp" className="min-h-[600px] p-4 bg-card rounded-2xl">
        <div className='flex pb-4'>
        <TabsList className='mb-4'>
          <TabsTrigger value="mcp">
            MCP Servers
            <Badge variant="outline" className="ml-auto text-xs">
              {vmcpConfig.vmcp_config.selected_servers?.length || 0}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="prompts">
            Prompts
            <Badge variant="outline" className="ml-auto text-xs">
              {(vmcpConfig.custom_prompts?.length || 0) + Object.values(vmcpConfig.vmcp_config.selected_prompts || {}).reduce((total, prompts) => total + (Array.isArray(prompts) ? prompts.length : 0), 0)}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="tools">Tools
            <Badge variant="outline" className="ml-auto text-xs">
              {(vmcpConfig.custom_tools?.length || 0) + Object.values(vmcpConfig.vmcp_config.selected_tools || {}).reduce((total, tools) => total + (Array.isArray(tools) ? tools.length : 0), 0)}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="resources">Resources
            <Badge variant="outline" className="ml-auto text-xs">
              {(vmcpConfig.uploaded_files?.length || 0) + Object.values(vmcpConfig.vmcp_config.selected_resources || {}).reduce((total, resources) => total + (Array.isArray(resources) ? resources.length : 0), 0)}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="env_vars">Config
            <Badge variant="outline" className="ml-auto text-xs">
              {vmcpConfig.environment_variables?.length || 0}
            </Badge>
          </TabsTrigger>
          {/* <TabsTrigger value="system">System</TabsTrigger> */}
        </TabsList>
        <div className="flex-1 w-full rounded-2xl">
            {!isNewVMCP && getVMCPUrl() && (
                <div className="flex w-fit pr-2 justify-self-end items-center gap-3 bg-muted rounded-2xl">
                  <span className="text-sm bg-background p-2 rounded-l-2xl">
                    vMCP url
                  </span>
                  <span className="text-sm text-muted-foreground font-mono max-w-5xl truncate">
                    {getVMCPUrl()}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleCopyUrl}
                    className="h-6 w-6 p-0 hover:bg-muted-foreground/20"
                    title="Copy URL to clipboard"
                  >
                    {urlCopied ? (
                      <Check className="h-3 w-3 text-green-600" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </Button>
                </div>
              )}
          </div>
        </div>
        <TabsContent value="system">
          <SystemTab
            vmcpConfig={vmcpConfig}
            setVmcpConfig={setVmcpConfig} 
            updateEnvironmentVariable={updateEnvironmentVariable}
            isRemoteVMCP={isRemoteVMCP}
          />
        </TabsContent>

        <TabsContent value="mcp">
          <MCPServersTab
            vmcpConfig={vmcpConfig}
            setVmcpConfig={setVmcpConfig}
            servers={servers}
            isRemoteVMCP={isRemoteVMCP}
            loadVMCPConfig={loadVMCPConfig}
          />
        </TabsContent>

        <TabsContent value="prompts">
          <PromptsTab
            vmcpConfig={vmcpConfig}
            servers={servers}
            isRemoteVMCP={isRemoteVMCP}
            addCustomPrompt={addCustomPrompt}
            removeCustomPrompt={removeCustomPrompt}
            setVmcpConfig={setVmcpConfig}
          />
        </TabsContent>

        <TabsContent value="tools">
          <ToolsTab
            vmcpConfig={vmcpConfig}
            servers={servers}
            isRemoteVMCP={isRemoteVMCP}
            expandedSections={expandedSections}
            setExpandedSections={setExpandedSections}
            addCustomTool={addCustomTool}
            removeCustomTool={removeCustomTool}
            setVmcpConfig={setVmcpConfig}
            forceRefreshVMCPData={forceRefreshVMCPData}
          />
        </TabsContent>

        <TabsContent value="resources">
          <ResourcesTab
            vmcpConfig={vmcpConfig}
            servers={servers}
            isRemoteVMCP={isRemoteVMCP}
            expandedSections={expandedSections}
            setExpandedSections={setExpandedSections}
            handleFileUpload={handleFileUpload}
            handleFileRemove={handleFileRemove}
            handleFileRename={handleFileRename}
            uploadingFiles={uploadingFiles}
            dragOver={dragOver}
            setDragOver={setDragOver}
            renamingFile={renamingFile}
            setRenamingFile={setRenamingFile}
            newFileName={newFileName}
            setNewFileName={setNewFileName}
            setVmcpConfig={setVmcpConfig}
          />
        </TabsContent>

        <TabsContent value="env_vars">
          <EnvironmentVariablesTab
            vmcpConfig={vmcpConfig}
            isRemoteVMCP={isRemoteVMCP}
            //addEnvironmentVariable={() => {}}
            removeEnvironmentVariable={removeEnvironmentVariable}
            updateEnvironmentVariable={updateEnvironmentVariable}
            setVmcpConfig={setVmcpConfig}
          />
        </TabsContent>
      </Tabs>

      {/* Delete Confirmation Modal */}
      <ConfirmationDialog
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleDelete}
        title="Delete vMCP"
        description={`Are you sure you want to delete "${vmcpConfig.name}"? This action cannot be undone.`}
        confirmText="Delete"
        variant="destructive"
        isLoading={deleting}
      />

      {/* Extend vMCP Dialog */}
      <Dialog open={showExtendDialog} onOpenChange={setShowExtendDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitFork className="h-5 w-5" />
              Extend vMCP
            </DialogTitle>
            <DialogDescription>
              A private copy of this vMCP will be created that you can modify and extend.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="extend-name">Name for your private copy</Label>
              <Input
                id="extend-name"
                type="text"
                value={extendName}
                onChange={(e) => setExtendName(e.target.value)}
                placeholder="Enter name for your private copy"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && extendName.trim()) {
                    handleExtendConfirm();
                  } else if (e.key === 'Escape') {
                    handleExtendCancel();
                  }
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleExtendCancel}
              disabled={forking}
              type="button"
            >
              Cancel
            </Button>
            <Button
              onClick={handleExtendConfirm}
              disabled={forking || !extendName.trim()}
              type="button"
            >
              {forking ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2"></div>
                  Creating...
                </>
              ) : (
                <>
                  <GitFork className="h-4 w-4 mr-2" />
                  Create Private Copy
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Header Modal */}
      <Dialog open={showEditHeaderModal} onOpenChange={setShowEditHeaderModal}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit vMCP Details</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="vmcp-name">
                Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="vmcp-name"
                type="text"
                value={editingName}
                onChange={(e) => setEditingName(e.target.value)}
                placeholder="Enter vMCP name"
                className="text-lg font-semibold"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="vmcp-description">Description</Label>
              <Textarea
                id="vmcp-description"
                value={editingDescription}
                onChange={(e) => setEditingDescription(e.target.value)}
                placeholder="Describe your vMCP"
                rows={3}
                className="resize-none"
              />
            </div>

            <div className="border-t border-border pt-4">
              <h4 className="text-sm font-medium text-foreground mb-3">Metadata</h4>
              <div className="space-y-3">
                {editingMetadata.map((item, index) => (
                  <div key={index} className="space-y-2">
                    <Label htmlFor={`metadata-${item.key}`} className="text-xs capitalize">
                      {item.key}
                    </Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id={`metadata-${item.key}`}
                        type="text"
                        value={item.value}
                        onChange={(e) => updateMetadataField(index, 'value', e.target.value)}
                        placeholder={item.key === 'icon' ? 'Icon URL or base64' : 'Author name'}
                        className="flex-1 h-9"
                      />
                      {item.key === 'icon' && item.value && (
                        <div className="flex-shrink-0">
                          {getIconDisplay(item.value)}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={cancelEditingHeader}
              type="button"
            >
              Cancel
            </Button>
            <Button
              onClick={saveHeaderEdit}
              disabled={!editingName.trim()}
              type="button"
            >
              <Save className="h-4 w-4 mr-2" />
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Changes Summary Dialog */}
      <Dialog open={showChangesSummaryDialog} onOpenChange={setShowChangesSummaryDialog}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Review Changes</DialogTitle>
            <DialogDescription>
              The following changes will be saved to your vMCP:
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-96 overflow-y-auto py-4">
                {!hasChanges ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No changes detected
                  </div>
                ) : (
                  <>
                    {changesSummary.updates.length > 0 && (
                      <div className="border border-border rounded-lg p-4 bg-blue-500/5">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="h-6 w-6 rounded-full bg-blue-500/20 flex items-center justify-center">
                            <span className="text-xs font-semibold text-blue-600 dark:text-blue-400">^</span>
                          </div>
                          <h4 className="font-semibold text-sm text-foreground">
                            Updates ({changesSummary.updates.length})
                          </h4>
                        </div>
                        <ul className="space-y-1.5 ml-8">
                          {changesSummary.updates.map((item, index) => (
                            <li key={index} className="text-sm text-muted-foreground flex items-start gap-2">
                              <span className="text-blue-500">•</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {changesSummary.additions.length > 0 && (
                      <div className="border border-border rounded-lg p-4 bg-green-500/5">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="h-6 w-6 rounded-full bg-green-500/20 flex items-center justify-center">
                            <span className="text-xs font-semibold text-green-600 dark:text-green-400">+</span>
                          </div>
                          <h4 className="font-semibold text-sm text-foreground">
                            Additions ({changesSummary.additions.length})
                          </h4>
                        </div>
                        <ul className="space-y-1.5 ml-8">
                          {changesSummary.additions.map((item, index) => (
                            <li key={index} className="text-sm text-muted-foreground flex items-start gap-2">
                              <span className="text-green-500">•</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {changesSummary.deletions.length > 0 && (
                      <div className="border border-border rounded-lg p-4 bg-red-500/5">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="h-6 w-6 rounded-full bg-red-500/20 flex items-center justify-center">
                            <span className="text-xs font-semibold text-red-600 dark:text-red-400">−</span>
                          </div>
                          <h4 className="font-semibold text-sm text-foreground">
                            Deletions ({changesSummary.deletions.length})
                          </h4>
                        </div>
                        <ul className="space-y-1.5 ml-8">
                          {changesSummary.deletions.map((item, index) => (
                            <li key={index} className="text-sm text-muted-foreground flex items-start gap-2">
                              <span className="text-red-500">•</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                )}
          </div>
          <DialogFooter className="flex-row justify-end gap-2">
            <Button
              variant="destructive"
              onClick={handleDiscardDraft}
              disabled={saving || !hasChanges}
              type="button"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Discard Changes
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              type="button"
            >
              {saving ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2"></div>
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Confirm & Save
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Discard Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={showDiscardConfirmDialog}
        onClose={() => setShowDiscardConfirmDialog(false)}
        onConfirm={confirmDiscardDraft}
        title="Discard Changes"
        description="Are you sure you want to discard all unsaved changes? This action cannot be undone."
        confirmText="Discard Changes"
        variant="destructive"
      />
    </div>
  );
}