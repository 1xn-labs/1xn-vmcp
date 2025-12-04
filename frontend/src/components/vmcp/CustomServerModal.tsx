// components/vmcp/CustomServerModal.tsx

import { Plus, X, RefreshCw, Terminal, Globe, Wifi } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { KeyValueInput } from '@/components/ui/key-value-input';

export interface CustomServerFormData {
  name: string;
  description: string;
  transport: 'stdio' | 'http' | 'sse';
  command: string;
  url: string;
  args: string;
  env: Array<{key: string, value: string}>;
  headers: Array<{key: string, value: string}>;
  auto_connect: boolean;
  enabled: boolean;
}

interface CustomServerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: () => Promise<void>;
  formData: CustomServerFormData;
  setFormData: React.Dispatch<React.SetStateAction<CustomServerFormData>>;
  isLoading?: boolean;
}

export function CustomServerModal({
  isOpen,
  onClose,
  onSubmit,
  formData,
  setFormData,
  isLoading = false
}: CustomServerModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-background border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-linear-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
              <Plus className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-foreground">Add Custom Server</h2>
              <p className="text-sm text-muted-foreground">Add a custom MCP server directly to this vMCP</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Server Name */}
            <div className="space-y-2 md:col-span-3">
              <Label htmlFor="server-name">Server Name *</Label>
              <Input
                id="server-name"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="my-custom-server"
                className="font-mono"
              />
            </div>

            {/* Transport Type */}
            <div className="space-y-2 md:col-span-1">
              <Label htmlFor="transport">Transport Type *</Label>
              <Select
                value={formData.transport}
                onValueChange={(value: 'stdio' | 'http' | 'sse') =>
                  setFormData(prev => ({ ...prev, transport: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue/>
                </SelectTrigger>
                <SelectContent>
                  {/* Enable stdio only for OSS builds */}
                  {import.meta.env.VITE_VMCP_OSS_BUILD && <SelectItem value="stdio">
                    <div className="flex items-center gap-2">
                      <Terminal className="h-4 w-4" />
                      stdio
                    </div>
                  </SelectItem>}
                  <SelectItem value="http">
                    <div className="flex items-center gap-2">
                      <Globe className="h-4 w-4" />
                      http
                    </div>
                  </SelectItem>
                  <SelectItem value="sse">
                    <div className="flex items-center gap-2">
                      <Wifi className="h-4 w-4" />
                      sse
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Brief description of what this server does..."
              rows={3}
            />
          </div>

          {/* Transport-specific fields */}
          {formData.transport === 'stdio' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="command">Command *</Label>
                <Input
                  id="command"
                  value={formData.command}
                  onChange={(e) => setFormData(prev => ({ ...prev, command: e.target.value }))}
                  placeholder="python -m my_mcp_server"
                  className="font-mono"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="args">Arguments (comma-separated)</Label>
                <Input
                  id="args"
                  value={formData.args}
                  onChange={(e) => setFormData(prev => ({ ...prev, args: e.target.value }))}
                  placeholder="--port,8080,--debug"
                  className="font-mono"
                />
              </div>
            </div>
          )}

          {(formData.transport === 'http' || formData.transport === 'sse') && (
            <div className="space-y-2">
              <Label htmlFor="url">URL *</Label>
              <Input
                id="url"
                value={formData.url}
                onChange={(e) => setFormData(prev => ({ ...prev, url: e.target.value }))}
                placeholder="https://api.example.com/mcp"
                className="font-mono"
              />
            </div>
          )}

          {/* Environment Variables or Headers based on transport */}
          {formData.transport === 'stdio' ? (
            <KeyValueInput
              label="Environment Variables"
              placeholder="Add environment variables"
              keyPlaceholder="Variable name"
              valuePlaceholder="Variable value"
              pairs={formData.env}
              onChange={(pairs) => setFormData(prev => ({ ...prev, env: pairs }))}
            />
          ) : (
            <KeyValueInput
              label="Headers"
              placeholder="Add custom headers"
              keyPlaceholder="Header name"
              valuePlaceholder="Header value"
              pairs={formData.headers}
              onChange={(pairs) => setFormData(prev => ({ ...prev, headers: pairs }))}
            />
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              onClick={onSubmit}
              disabled={isLoading || !formData.name.trim()}
              className="flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4" />
                  Add to vMCP
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
