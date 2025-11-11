
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';
import { useToast } from '@/hooks/use-toast';
// import { apiClient } from '@/api/client'; // Using newApi instead
// import { newApi } from '@/lib/new-api';
// import type { VMCPCreateRequest } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import type { VmcpCreateRequest as VMCPCreateRequest } from '@/api/generated/types.gen';
import { useRouter } from '@/hooks/useRouter';
import { Loader2 } from 'lucide-react';

interface CreateVMCPModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (vmcpId: string) => void;
}

export default function CreateVMCPModal({ isOpen, onClose, onSuccess }: CreateVMCPModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const { success, error: toastError } = useToast();
  const router = useRouter();

  // Debug logging
  console.log('[CreateVMCPModal] Component rendered, isOpen:', isOpen);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!name.trim()) {
      toastError('vMCP name is required');
      return;
    }

    setLoading(true);
    
    try {
      const accessToken = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      if (!accessToken) {
        toastError('Please log in to create vMCPs');
        return;
      }

      // Create vMCP with default system prompt matching VMCPCreateRequest type
      const vmcpData: VMCPCreateRequest = {
        name: name.trim(),
        description: description.trim() || undefined,
        system_prompt: {
          text: `You are a helpful AI assistant with access to various tools and resources. You can help users with a wide range of tasks using the available MCP (Model Context Protocol) tools.\n\nAvailable capabilities:\n- Execute tools to perform specific actions\n- Access resources for information\n- Use prompts for structured interactions\n\nAlways be helpful, accurate, and explain what you're doing when using tools.`,
          variables: [],
          environment_variables: [],
          tool_calls: []
        },
        vmcp_config: {
          selected_servers: [],
          selected_tools: {},
          selected_prompts: {},
          selected_resources: {}
        },
        custom_prompts: undefined,
        custom_tools: undefined,
        custom_context: undefined,
        custom_resources: undefined,
        custom_resource_uris: undefined,
        environment_variables: undefined,
        uploaded_files: undefined
      };

      const result = await apiClient.createVMCP(vmcpData, accessToken);

      if (result.success && result.data?.id) {
        const vmcpId = result.data.id;
        success(`vMCP "${name}" created successfully!`);
        onClose();
        setName('');
        setDescription('');
        
        // Navigate to the new vMCP
        if (onSuccess) {
          onSuccess(vmcpId);
        } else {
          router.push(`/vmcp/${vmcpId}`);
        }
      } else {
        throw new Error(result.error || 'Failed to create vMCP');
      }
    } catch (error) {
      console.error('Error creating vMCP:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create vMCP';
      toastError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
      setName('');
      setDescription('');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Create New vMCP" size="sm">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Create a new virtual Model Context Protocol configuration. You can add servers and configure tools later.
        </p>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="name">
              Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My vMCP"
              disabled={loading}
              required
            />
          </div>
          
          <div className="grid gap-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what this vMCP will be used for..."
              rows={3}
              disabled={loading}
            />
          </div>
          
          <div className="flex justify-end gap-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create vMCP'
              )}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
