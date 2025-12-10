// components/vmcp/ProgressiveDiscoveryTab.tsx

import { useState, useEffect } from 'react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { VMCPConfig } from '@/types/vmcp';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';

interface ProgressiveDiscoveryTabProps {
  vmcpConfig: VMCPConfig;
  vmcpId: string;
  isRemoteVMCP?: boolean;
  onProgressiveDiscoveryStatusChange?: (enabled: boolean) => void;
}

export default function ProgressiveDiscoveryTab({
  vmcpConfig,
  vmcpId,
  isRemoteVMCP = false,
  onProgressiveDiscoveryStatusChange,
}: ProgressiveDiscoveryTabProps) {
  const [progressiveDiscoveryEnabled, setProgressiveDiscoveryEnabled] = useState(false);
  const [togglingProgressiveDiscovery, setTogglingProgressiveDiscovery] = useState(false);
  const { success: showSuccess, error: showError } = useToast();

  // Load progressive discovery status
  useEffect(() => {
    if (!vmcpId || vmcpId === 'new') {
      setProgressiveDiscoveryEnabled(false);
      return;
    }

    const loadProgressiveDiscoveryStatus = async () => {
      try {
        const accessToken = localStorage.getItem('access_token') || 
          (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
        const result = await apiClient.getProgressiveDiscoveryStatus(vmcpId, accessToken);
        if (result.success && result.data) {
          setProgressiveDiscoveryEnabled(result.data.enabled);
        }
      } catch (error) {
        console.error('Error loading progressive discovery status:', error);
      }
    };

    loadProgressiveDiscoveryStatus();
  }, [vmcpId]);

  const handleToggleProgressiveDiscovery = async (checked: boolean) => {
    try {
      setTogglingProgressiveDiscovery(true);
      const accessToken = localStorage.getItem('access_token') || 
        (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);

      if (checked) {
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

  return (
    <div className="flex flex-col h-full min-h-0 flex-1 overflow-hidden bg-background">
      <div className="flex-shrink-0 flex flex-col gap-3 p-4 border-b border-border bg-muted/50">
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
        
        {progressiveDiscoveryEnabled && (
          <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
            <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
              Progressive Discovery Enabled
            </h3>
            <p className="text-xs text-blue-800 dark:text-blue-200">
              When Progressive Discovery is enabled, only three tools are available:
            </p>
            <ul className="mt-2 text-xs text-blue-800 dark:text-blue-200 list-disc list-inside space-y-1">
              <li><strong>tools_list</strong> - List all available tools</li>
              <li><strong>tool_detail(tool_name)</strong> - Get detailed information about a specific tool</li>
              <li><strong>upload_prompt</strong> - Upload a new prompt to the vMCP</li>
            </ul>
            <p className="mt-2 text-xs text-blue-800 dark:text-blue-200">
              All other MCP tools and custom tools are hidden until Progressive Discovery is disabled.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

