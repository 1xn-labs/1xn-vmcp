// components/vmcp/SandboxTab.tsx

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { VMCPConfig, FileNode } from '@/types/vmcp';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';
import { ConfirmationDialog } from '@/components/ui/confirmation-dialog';
import FileTree from './FileTree';
import CodeEditor from './CodeEditor';
import Terminal from './Terminal';
import EmptySandboxState from './EmptySandboxState';
import { getFileIcon } from '@/utils/fileIcons';
import { Trash2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface SandboxTabProps {
  vmcpConfig: VMCPConfig;
  vmcpId: string;
  isRemoteVMCP?: boolean;
  onSandboxStatusChange?: (enabled: boolean) => void;
  onProgressiveDiscoveryStatusChange?: (enabled: boolean) => void;
}

export default function SandboxTab({ vmcpConfig, vmcpId, isRemoteVMCP = false, onSandboxStatusChange, onProgressiveDiscoveryStatusChange }: SandboxTabProps) {
  const [sandboxEnabled, setSandboxEnabled] = useState(false);
  const [progressiveDiscoveryEnabled, setProgressiveDiscoveryEnabled] = useState(false);
  const [folderExists, setFolderExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [enabling, setEnabling] = useState(false);
  const [togglingProgressiveDiscovery, setTogglingProgressiveDiscovery] = useState(false);
  const [files, setFiles] = useState<FileNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingFileContent, setLoadingFileContent] = useState(false);
  const [cursorPosition, setCursorPosition] = useState({ line: 1, column: 1 });
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [activeTab, setActiveTab] = useState('files');
  const { success: showSuccess, error: showError } = useToast();

  // Load files with lazy loading support
  const loadFiles = useCallback(async (path: string = '', updateTree: boolean = true) => {
    try {
      setLoadingFiles(true);
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.listSandboxFiles(vmcpId, path, accessToken);

      if (result.success && result.data) {
        // Transform API response to properly typed FileNode array
        const typedFiles = result.data.map(transformToFileNode);
        
        if (updateTree) {
          if (path === '') {
            // Root level - replace all files
            setFiles(typedFiles);
          } else {
            // Update specific path in tree (for lazy loading)
            const updateFileTreeAtPath = (nodes: FileNode[], targetPath: string, newChildren: FileNode[]): FileNode[] => {
              return nodes.map(node => {
                if (node.path === targetPath && node.type === 'directory') {
                  return { ...node, children: newChildren };
                }
                if (node.children) {
                  return { ...node, children: updateFileTreeAtPath(node.children, targetPath, newChildren) };
                }
                return node;
              });
            };
            
            setFiles(prevFiles => updateFileTreeAtPath(prevFiles, path, typedFiles));
          }
        } else {
          // Just return the files without updating state (for lazy loading)
          return typedFiles;
        }
      }
    } catch (error) {
      console.error('Error loading files:', error);
      showError('Failed to load files');
    } finally {
      setLoadingFiles(false);
    }
  }, [vmcpId, showError]);

  // Helper function to transform API response to FileNode
  const transformToFileNode = (node: any): FileNode => {
    return {
      name: node.name,
      path: node.path,
      type: (node.type === 'directory' ? 'directory' : 'file') as 'file' | 'directory',
      children: node.children ? node.children.map(transformToFileNode) : undefined,
      size: node.size,
      modified: node.modified,
    };
  };

  // Load sandbox status
  const loadSandboxStatus = useCallback(async () => {
    try {
      setLoading(true);
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.getSandboxStatus(vmcpId, accessToken);

      if (result.success && result.data) {
        setSandboxEnabled(result.data.enabled);
        if (onSandboxStatusChange) {
          onSandboxStatusChange(result.data.enabled);
        }
        setFolderExists(result.data.folder_exists || false);
        // If folder exists, load files (regardless of enabled flag)
        if (result.data.folder_exists) {
          await loadFiles();
        }
      }
    } catch (error) {
      console.error('Error loading sandbox status:', error);
    } finally {
      setLoading(false);
    }
  }, [vmcpId, loadFiles]);

  // Load progressive discovery status
  const loadProgressiveDiscoveryStatus = useCallback(async () => {
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.getProgressiveDiscoveryStatus(vmcpId, accessToken);

      if (result.success && result.data) {
        setProgressiveDiscoveryEnabled(result.data.enabled);
        if (onProgressiveDiscoveryStatusChange) {
          onProgressiveDiscoveryStatusChange(result.data.enabled);
        }
      }
    } catch (error) {
      console.error('Error loading progressive discovery status:', error);
    }
  }, [vmcpId, onProgressiveDiscoveryStatusChange]);

  // Find file node by path to check if it's a directory
  const findFileNode = (path: string, nodes: FileNode[]): FileNode | null => {
    for (const node of nodes) {
      if (node.path === path) {
        return node;
      }
      if (node.children) {
        const found = findFileNode(path, node.children);
        if (found) return found;
      }
    }
    return null;
  };

  // Load file content
  const loadFileContent = useCallback(async (filePath: string) => {
    try {
      setLoadingFileContent(true);

      // Check if the selected item is a directory (only if files are loaded)
      if (files.length > 0) {
        const fileNode = findFileNode(filePath, files);
        if (fileNode && fileNode.type === 'directory') {
          setFileContent('');
          setLoadingFileContent(false);
          return;
        }
      }

      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.getSandboxFile(vmcpId, filePath, accessToken);

      if (result.success && result.data) {
        const content = result.data.content;
        // Ensure content is a string
        const contentStr = typeof content === 'string' ? content : String(content || '');
        setFileContent(contentStr);
      } else {
        console.error('Failed to load file:', result.error, result);
        showError(result.error || 'Failed to load file');
        setFileContent('');
      }
    } catch (error) {
      console.error('Error loading file content:', error);
      showError('Failed to load file content');
      setFileContent('');
    } finally {
      setLoadingFileContent(false);
    }
  }, [vmcpId, showError, files]);

  // Handle file selection
  useEffect(() => {
    if (selectedFile) {
      loadFileContent(selectedFile);
    } else {
      setFileContent('');
    }
  }, [selectedFile, loadFileContent]);

  // Initial load - only load files if folder exists
  useEffect(() => {
    loadSandboxStatus();
    loadProgressiveDiscoveryStatus();
  }, [loadSandboxStatus, loadProgressiveDiscoveryStatus]);

  // Memoize file tree to prevent unnecessary re-renders
  const memoizedFiles = useMemo(() => files, [files]);

  // Handle toggle sandbox (enable/disable)
  const handleToggleSandbox = async (checked: boolean) => {
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);

      if (checked) {
        // Enable sandbox
        setEnabling(true);
        const result = await apiClient.enableSandbox(vmcpId, accessToken);

        if (result.success) {
          setSandboxEnabled(true);
          if (onSandboxStatusChange) {
            onSandboxStatusChange(true);
          }
          setFolderExists(true);
          showSuccess('Sandbox enabled successfully');
          await loadFiles();
        } else {
          showError(result.error || 'Failed to enable sandbox');
        }
        setEnabling(false);
      } else {
        // Disable sandbox
        const result = await apiClient.disableSandbox(vmcpId, accessToken);

        if (result.success) {
          setSandboxEnabled(false);
          if (onSandboxStatusChange) {
            onSandboxStatusChange(false);
          }
          // Don't clear files or folder - just update the flag
          showSuccess('Sandbox disabled successfully');
          // Reload status to sync with backend - Removed to prevent full reload
          // await loadSandboxStatus();
        } else {
          showError(result.error || 'Failed to disable sandbox');
        }
      }
    } catch (error) {
      console.error('Error toggling sandbox:', error);
      showError(`Failed to ${checked ? 'enable' : 'disable'} sandbox`);
      if (checked) {
        setEnabling(false);
      }
    }
  };

  // Handle toggle progressive discovery (enable/disable)
  const handleToggleProgressiveDiscovery = async (checked: boolean) => {
    try {
      setTogglingProgressiveDiscovery(true);
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);

      if (checked) {
        // Enable progressive discovery
        const result = await apiClient.enableProgressiveDiscovery(vmcpId, accessToken);

        if (result.success) {
          setProgressiveDiscoveryEnabled(true);
          if (onProgressiveDiscoveryStatusChange) {
            onProgressiveDiscoveryStatusChange(true);
          }
          showSuccess('Progressive discovery enabled successfully');
        } else {
          showError(result.error || 'Failed to enable progressive discovery');
        }
      } else {
        // Disable progressive discovery
        const result = await apiClient.disableProgressiveDiscovery(vmcpId, accessToken);

        if (result.success) {
          setProgressiveDiscoveryEnabled(false);
          if (onProgressiveDiscoveryStatusChange) {
            onProgressiveDiscoveryStatusChange(false);
          }
          showSuccess('Progressive discovery disabled successfully');
        } else {
          showError(result.error || 'Failed to disable progressive discovery');
        }
      }
    } catch (error) {
      console.error('Error toggling progressive discovery:', error);
      showError(`Failed to ${checked ? 'enable' : 'disable'} progressive discovery`);
    } finally {
      setTogglingProgressiveDiscovery(false);
    }
  };

  // Handle save file
  const handleSaveFile = async () => {
    if (!selectedFile) return;

    try {
      setSaving(true);
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.saveSandboxFile(vmcpId, selectedFile, fileContent, accessToken);

      if (result.success) {
        showSuccess('File saved successfully');
        await loadFiles(); // Refresh file tree
      } else {
        showError(result.error || 'Failed to save file');
      }
    } catch (error) {
      console.error('Error saving file:', error);
      showError('Failed to save file');
    } finally {
      setSaving(false);
    }
  };

  // Handle file upload
  const handleFileUpload = async (fileList: FileList) => {
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);

      for (const file of Array.from(fileList)) {
        const result = await apiClient.uploadSandboxFile(vmcpId, file, undefined, accessToken);

        if (result.success) {
          showSuccess(`File ${file.name} uploaded successfully`);
        } else {
          showError(result.error || `Failed to upload ${file.name}`);
        }
      }

      await loadFiles(); // Refresh file tree
    } catch (error) {
      console.error('Error uploading files:', error);
      showError('Failed to upload files');
    }
  };

  // Handle file delete
  const handleFileDelete = async (filePath: string) => {
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.deleteSandboxFile(vmcpId, filePath, accessToken);

      if (result.success) {
        showSuccess('File deleted successfully');
        if (selectedFile === filePath) {
          setSelectedFile(null);
          setFileContent('');
        }
        await loadFiles(); // Refresh file tree
      } else {
        showError(result.error || 'Failed to delete file');
      }
    } catch (error) {
      console.error('Error deleting file:', error);
      showError('Failed to delete file');
    }
  };

  // Handle create new file
  const handleCreateFile = async (filePath: string) => {
    try {
      // Normalize path (remove leading slash if present)
      const normalizedPath = filePath.startsWith('/') ? filePath.slice(1) : filePath;

      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.saveSandboxFile(vmcpId, normalizedPath, '', accessToken);

      if (result.success) {
        showSuccess('File created successfully');
        await loadFiles(); // Refresh file tree
        setSelectedFile(normalizedPath);
        setFileContent(''); // Empty content for new file
      } else {
        showError(result.error || 'Failed to create file');
      }
    } catch (error) {
      console.error('Error creating file:', error);
      showError('Failed to create file');
    }
  };

  // Handle create new folder
  const handleCreateFolder = async (folderPath: string) => {
    try {
      // Normalize path (remove leading slash if present)
      const normalizedPath = folderPath.startsWith('/') ? folderPath.slice(1) : folderPath;

      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.createSandboxFolder(vmcpId, normalizedPath, accessToken);

      if (result.success) {
        showSuccess('Folder created successfully');
        await loadFiles(); // Refresh file tree
      } else {
        showError(result.error || 'Failed to create folder');
      }
    } catch (error) {
      console.error('Error creating folder:', error);
      showError('Failed to create folder');
    }
  };

  // Update cursor position from CodeEditor
  const handleCursorChange = useCallback((line: number, column: number) => {
    setCursorPosition({ line, column });
  }, []);

  // Handle delete sandbox
  const handleDeleteSandbox = async () => {
    try {
      setDeleting(true);
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      const result = await apiClient.deleteSandbox(vmcpId, accessToken);

      if (result.success) {
        // Update state to reflect sandbox deletion
        setSandboxEnabled(false);
        if (onSandboxStatusChange) {
          onSandboxStatusChange(false);
        }
        setFolderExists(false);
        setFiles([]);
        setSelectedFile(null);
        setFileContent('');
        setShowDeleteDialog(false);
        showSuccess('Sandbox deleted successfully');
        // Reload status to ensure everything is in sync with backend
        // This will verify the folder is actually deleted and update UI accordingly
        try {
          await loadSandboxStatus();
        } catch (error) {
          // If status load fails, that's okay - we've already updated local state
          console.warn('Failed to reload sandbox status after deletion:', error);
        }
      } else {
        showError(result.error || 'Failed to delete sandbox');
      }
    } catch (error) {
      console.error('Error deleting sandbox:', error);
      showError('Failed to delete sandbox');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading sandbox...</p>
        </div>
      </div>
    );
  }

  // Show empty state only if folder doesn't exist
  if (!folderExists) {
    return <EmptySandboxState onEnable={() => handleToggleSandbox(true)} loading={enabling} />;
  }

  const language = selectedFile ? (() => {
    const ext = selectedFile.split('.').pop()?.toLowerCase();
    const languageMap: Record<string, string> = {
      'py': 'python', 'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'typescript',
      'json': 'json', 'yaml': 'yaml', 'yml': 'yaml', 'md': 'markdown', 'html': 'html', 'css': 'css',
      'sh': 'shell', 'bash': 'shell', 'sql': 'sql', 'xml': 'xml', 'toml': 'toml', 'ini': 'ini', 'txt': 'plaintext',
    };
    return languageMap[ext || ''] || 'plaintext';
  })() : 'plaintext';
  const fileType = language.charAt(0).toUpperCase() + language.slice(1);

  return (
    <div className="flex flex-col h-full min-h-0 flex-1 overflow-hidden bg-background">
      {/* Toggle switches */}
      <div className="flex-shrink-0 flex flex-col gap-3 p-4 border-b border-border bg-muted/50">
        {/* Sandbox Toggle */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Switch
              id="sandbox-toggle"
              checked={sandboxEnabled}
              onCheckedChange={handleToggleSandbox}
              disabled={isRemoteVMCP || enabling}
            />
            <Label htmlFor="sandbox-toggle" className="text-sm font-medium">
              {sandboxEnabled ? 'Disable Sandbox' : 'Enable Sandbox'}
            </Label>
          </div>
          <div className="flex items-center gap-3">
            {isRemoteVMCP && (
              <p className="text-xs text-muted-foreground">
                Sandbox cannot be disabled for remote vMCPs
              </p>
            )}
            {folderExists && !isRemoteVMCP && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowDeleteDialog(true)}
                disabled={deleting || enabling}
                className="gap-2"
              >
                <Trash2 className="h-4 w-4" />
                Delete Sandbox
              </Button>
            )}
          </div>
        </div>

        {/* Progressive Discovery Toggle */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Switch
              id="progressive-discovery-toggle"
              checked={progressiveDiscoveryEnabled}
              onCheckedChange={handleToggleProgressiveDiscovery}
              disabled={isRemoteVMCP || togglingProgressiveDiscovery}
            />
            <Label htmlFor="progressive-discovery-toggle" className="text-sm font-medium">
              {progressiveDiscoveryEnabled ? 'Disable Progressive Discovery' : 'Enable Progressive Discovery'}
            </Label>
          </div>
        </div>
      </div>

      {/* Main content: Tabs for Files and Terminal */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col flex-1 min-h-0">
        <TabsList className="mx-4 mt-2 mb-0">
          <TabsTrigger value="files">Files</TabsTrigger>
          <TabsTrigger value="terminal">Terminal</TabsTrigger>
        </TabsList>
        
        <TabsContent value="files" className="flex flex-1 min-h-0 mt-0 overflow-hidden">
          <div className="flex flex-1 min-h-0 overflow-hidden">
            <FileTree
              files={memoizedFiles}
              selectedPath={selectedFile}
              onSelect={setSelectedFile}
              onDelete={handleFileDelete}
              onUpload={handleFileUpload}
              onCreateFile={handleCreateFile}
              onCreateFolder={handleCreateFolder}
              loading={loadingFiles}
            />
            <CodeEditor
              filePath={selectedFile}
              content={fileContent}
              onChange={setFileContent}
              onSave={handleSaveFile}
              saving={saving}
              loading={loadingFileContent}
              readOnly={isRemoteVMCP}
              onCursorChange={handleCursorChange}
            />
          </div>
        </TabsContent>
        
        {/* Terminal - always mounted but hidden when not active to preserve WebSocket connection */}
        <div className={activeTab === 'terminal' ? 'flex flex-1 min-h-0 mt-0 p-4 overflow-hidden' : 'hidden'}>
          <Terminal vmcpId={vmcpId} className="h-full" />
        </div>
      </Tabs>

      {/* Status Bar - Fixed at bottom, spans full width */}
      <div className="flex-shrink-0 border-t border-border px-4 py-0.5 flex items-center justify-between bg-muted/50 text-xs text-muted-foreground h-6">
        <div className="flex items-center gap-4">
          <span className="truncate">{selectedFile || 'No file selected'}</span>
        </div>
        <div className="flex items-center gap-4">
          <span>{fileType}</span>
          <span>Ln {cursorPosition.line}, Col {cursorPosition.column}</span>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        onConfirm={handleDeleteSandbox}
        title="Delete Sandbox"
        description="This will permanently delete the sandbox directory and all its contents. This action cannot be undone. The sandbox will be disabled after deletion."
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
        isLoading={deleting}
      />
    </div>
  );
}
