// components/EnvironmentVariablesTab.tsx

import { Zap, Plus, Trash2, Edit, Save, X } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { VMCPConfig } from '@/types/vmcp';
import { renameEnvironmentVariable } from '@/lib/vmcp';
import { useToast } from '@/hooks/use-toast';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

interface EnvironmentVariablesTabProps {
  vmcpConfig: VMCPConfig;
  //addEnvironmentVariable: () => void;
  removeEnvironmentVariable: (index: number) => void;
  updateEnvironmentVariable: (index: number, field: 'name' | 'value' | 'description' | 'required' | 'source', value: string | boolean) => void;
  setVmcpConfig: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
  isRemoteVMCP?: boolean;
}

export default function EnvironmentVariablesTab({
  vmcpConfig,
  removeEnvironmentVariable,
  updateEnvironmentVariable,
  setVmcpConfig,
  isRemoteVMCP = false,
}: EnvironmentVariablesTabProps) {
  const [showModal, setShowModal] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [modalName, setModalName] = useState('');
  const [modalValue, setModalValue] = useState('');
  const [modalDescription, setModalDescription] = useState('');
  const [modalRequired, setModalRequired] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const { toast } = useToast();

  const handleAddNew = () => {
    setEditingIndex(null);
    setModalName('');
    setModalValue('');
    setModalDescription('');
    setModalRequired(false);
    setShowModal(true);
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
      
      updateEnvironmentVariable(editingIndex, 'name', newName);
      updateEnvironmentVariable(editingIndex, 'value', modalValue);
      updateEnvironmentVariable(editingIndex, 'description', modalDescription);
      updateEnvironmentVariable(editingIndex, 'required', modalRequired);
    } else {
      // Adding new variable
      setVmcpConfig(prev => ({
        ...prev,
        environment_variables: [...prev.environment_variables, {
          name: modalName.trim(),
          value: modalValue,
          description: modalDescription,
          required: modalRequired,
          source: 'manual'
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

  const handleSaveEnvironmentVariables = async () => {
    if (!isRemoteVMCP) return;
    
    setIsSaving(true);
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        toast.error("Please log in to save environment variables");
        return;
      }

      const result = await apiClient.saveVMCPEnvironmentVariables(
        vmcpConfig.id,
        vmcpConfig.environment_variables,
        token
      );

      if (result.success) {
        toast.success(result.data?.message || "Environment variables saved successfully");
      } else {
        toast.error(result.error || "Failed to save environment variables");
      }
    } catch (error) {
      console.error('Error saving environment variables:', error);
      toast.error("Failed to save environment variables");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
        <Zap className="h-5 w-5 text-primary" />
        Config Variables
      </h2>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-muted-foreground">
            {isRemoteVMCP 
              ? "Configure environment variables for this remote vMCP. Edit the values below and click 'Save Variables' to persist your changes.  "
              : "Define config variables for this vMCP. These variables can be referenced in your prompts, tools, and system prompt using @env(CONFIG_VAR) syntax."
            }
          </p>
          {isRemoteVMCP ? (
            <Button
              size="sm"
              onClick={handleSaveEnvironmentVariables}
              disabled={isSaving}
              title="Save environment variables to backend"
            >
              <Save className="h-4 w-4 mr-2" />
              {isSaving ? 'Saving...' : 'Save Config'}
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={handleAddNew}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Config Variable
            </Button>
          )}
        </div>

        {vmcpConfig.environment_variables.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Zap className="h-8 w-8 mx-auto mb-4 text-muted-foreground" />
            <p className="text-lg font-medium text-foreground mb-2">No config variables defined yet</p>
            {isRemoteVMCP ? (
              <p className="text-muted-foreground mb-4">This remote vMCP doesn't have any config variables defined. You can only edit values for existing variables.</p>
            ) : (
              <p className="text-muted-foreground mb-4">Click "Add Variable" to create your first config variable.</p>
            )}
            <p className="text-sm text-muted-foreground">
              Config variables can be referenced in your content using <code className="bg-muted px-1 rounded">@env(CONFIG_VAR)</code> syntax.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {vmcpConfig.environment_variables.map((envVar, index) => (
              <div className="flex flex-col border p-4 rounded-2xl mb-3 gap-2">
                <div className="flex justify-between gap-2">
                  <span className="flex-1 font-bold">{envVar.name}</span>
                    <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleEdit(index)}
                    className="h-6 w-6 p-0"
                    disabled={isRemoteVMCP}
                    title={isRemoteVMCP ? 'Editing disabled for remote vMCPs' : ''}
                  >
                    <Edit className="h-3 w-3" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => removeEnvironmentVariable(index)}
                    className="h-7 px-2 hover:text-destructive/80"
                    disabled={isRemoteVMCP}
                    title={isRemoteVMCP ? 'Removing variables disabled for remote vMCPs' : ''}
                  >
                  <Trash2 className="h-3 w-3" />
                </Button>
                </div>
                <div className="text-sm text-muted-foreground">
                  {envVar.description || 'No description'}
                </div>
                <Input
                  type="text"
                  value={envVar.value || ''}
                  onChange={(e) => updateEnvironmentVariable(index, 'value', e.target.value)}
                  placeholder="Enter value"
                  className={envVar.value === "<<NEED_INPUT_FROM_USER>>" || envVar.value === '' ? "mt-1 h-7 text-sm border border-destructive/70" : 'mt-1 h-7 text-sm'}
                />
                {/* Usage info */}
                {!isRemoteVMCP && (<div className="text-xs text-muted-foreground">
                  <span className="font-medium">Usage:</span> Use <code className="bg-muted px-1 rounded">@env({envVar.name})</code> in your prompts, tools, or system prompt.
                </div>)}
              </div>
            ))}
          </div>
        )}
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
                  id="required"
                  checked={modalRequired}
                  onCheckedChange={(checked: boolean) => setModalRequired(checked)}
                />
                <Label htmlFor="required" className="text-sm font-medium">
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
    </div>
  );
}