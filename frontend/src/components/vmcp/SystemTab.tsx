// components/SystemTab.tsx

import { Star, Save, Plus, Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import VMCPMonacoEditor from '@/components/editor/VMCPMonacoEditor';
import { VMCPConfig } from '@/types/vmcp';
import { Label } from '@/components/ui/label';
import { useState } from 'react';
import { renameEnvironmentVariable } from '@/lib/vmcp';

interface SystemTabProps {
  vmcpConfig: VMCPConfig;
  setVmcpConfig: (config: VMCPConfig | ((prev: VMCPConfig) => VMCPConfig)) => void;
  updateEnvironmentVariable: (index: number, field: 'name' | 'value' | 'description' | 'required' | 'source', value: string | boolean) => void;
  isRemoteVMCP?: boolean;
}

export default function SystemTab({
  vmcpConfig,
  setVmcpConfig,
  updateEnvironmentVariable,
  isRemoteVMCP = false
}: SystemTabProps) {
  const [showModal, setShowModal] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [modalName, setModalName] = useState('');
  const [modalValue, setModalValue] = useState('');
  const [modalDescription, setModalDescription] = useState('');
  const [modalRequired, setModalRequired] = useState(false);
  const [showVariableModal, setShowVariableModal] = useState(false);
  const [variableModalName, setVariableModalName] = useState('');
  const [variableModalDescription, setVariableModalDescription] = useState('');
  const [variableModalRequired, setVariableModalRequired] = useState(false);
  const [variableModalType, setVariableModalType] = useState<'add' | 'edit'>('add');
  const [editingVariableIndex, setEditingVariableIndex] = useState<number | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const handleAddEnvironmentVariable = (name: string) => {
    const existingIndex = vmcpConfig.environment_variables.findIndex(ev => ev.name === name);
    if (existingIndex >= 0) {
      // If it exists, update its value
      updateEnvironmentVariable(existingIndex, 'value', '');
    } else {
      // If it doesn't exist, add it
      setVmcpConfig(prev => ({
        ...prev,
        environment_variables: [...prev.environment_variables, { 
          name: name, 
          value: '', 
          description: '', 
          required: false, 
          source: 'manual' 
        }]
      }));
    }
  };

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
      
      // Update the environment variable
      setVmcpConfig(prev => ({
        ...prev,
        environment_variables: prev.environment_variables.map((ev, i) => 
          i === editingIndex ? { ...ev, name: newName, value: modalValue, description: modalDescription, required: modalRequired } : ev
        )
      }));
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

  const handleAddVariable = () => {
    setVariableModalType('add');
    setVariableModalName('');
    setVariableModalDescription('');
    setVariableModalRequired(false);
    setEditingVariableIndex(null);
    setShowVariableModal(true);
  };

  const handleEditVariable = (index: number) => {
    if (!vmcpConfig.system_prompt.variables) vmcpConfig.system_prompt.variables = [];
    
    const variable = vmcpConfig.system_prompt.variables[index];
    setVariableModalType('edit');
    setVariableModalName(variable.name);
    setVariableModalDescription(variable.description || '');
    setVariableModalRequired(variable.required || false);
    setEditingVariableIndex(index);
    setShowVariableModal(true);
  };

  const handleSaveVariable = () => {
    if (!variableModalName.trim()) return;

    if (!vmcpConfig.system_prompt.variables) vmcpConfig.system_prompt.variables = [];

    if (variableModalType === 'edit' && editingVariableIndex !== null) {
      // Editing existing variable
      const oldName = vmcpConfig.system_prompt.variables[editingVariableIndex].name;
      const newName = variableModalName.trim();
      
      if (newName !== oldName) {
        // Rename variable in system prompt text
        const newText = vmcpConfig.system_prompt.text.replace(new RegExp(`var\\(${oldName}\\)`, 'g'), `var(${newName})`);
        vmcpConfig.system_prompt.text = newText;
      }
      
      // Update the variable
      vmcpConfig.system_prompt.variables[editingVariableIndex] = {
        name: newName,
        description: variableModalDescription,
        required: variableModalRequired
      };
    } else {
      // Adding new variable
      vmcpConfig.system_prompt.variables.push({
        name: variableModalName.trim(),
        description: variableModalDescription,
        required: variableModalRequired
      });
    }
    
    // Update the VMCP config
    setVmcpConfig(prev => ({
      ...prev,
      system_prompt: vmcpConfig.system_prompt
    }));
    
    setShowVariableModal(false);
  };

  const handleCancelVariable = () => {
    setShowVariableModal(false);
    setVariableModalName('');
    setVariableModalDescription('');
    setVariableModalRequired(false);
    setEditingVariableIndex(null);
  };

  const removeVariable = (index: number) => {
    if (!vmcpConfig.system_prompt.variables) return;
    
    // Remove the variable from the variables array only
    vmcpConfig.system_prompt.variables.splice(index, 1);
    
    // Update the VMCP config
    setVmcpConfig(prev => ({
      ...prev,
      system_prompt: vmcpConfig.system_prompt
    }));
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      {/* System Prompt Content */}
      <div className='flex-1 gap-16 min-w-2xl'>
        {/* Sys prompt editor */}
        <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Star className="h-5 w-5 text-primary" />
            System Prompt
          </div>
        </h2>
        <div className="flex items-center justify-between mb-2">
          <p className="text-muted-foreground">
            Define the system prompt for your vMCP. This is required and sets the behavior of your agent.
          </p>
          {hasUnsavedChanges && (
            <Button
            onClick={() => {setVmcpConfig(prev => {
              console.log("Saving system prompt ==========", vmcpConfig.system_prompt.text);
              return {
                ...prev,
                system_prompt: {
                  ...prev.system_prompt,
                  text: vmcpConfig.system_prompt.text
                }
                
              };
              
            });
            setHasUnsavedChanges(false);
          }}
            size="sm"
            variant="outline"
          >
            <Save className="h-4 w-4 mr-2" />
            Save Draft
          </Button>
          )}
        </div>
        <VMCPMonacoEditor 
          className='border bg-background/50 p-2'
          value={vmcpConfig.system_prompt.text}
          onChange={(text) => {
            if (!isRemoteVMCP) {
              // console.log("Text changed ==========", text);
              vmcpConfig.system_prompt.text = text;
              setHasUnsavedChanges(true);
            }
          }}
          height={480}
          vmcpConfig={vmcpConfig}
          editKey="system_prompt"
          readOnly={isRemoteVMCP}
        />
      </div>
      
      {/* Variables */}
      <div className='flex gap-2 basis-sm flex-col'>
        {/* Parameters Display */}
        <div className="bg-card p-2 rounded-2xl">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-medium underline underline-offset-4 decoration-accent text-foreground">Parameters</h4>
            {!isRemoteVMCP && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleAddVariable}
                className="h-6 w-6 p-0"
              >
                <Plus className="h-3 w-3" />
              </Button>
            )}
          </div>
          <div className="space-y-2">
            {vmcpConfig.system_prompt.variables && vmcpConfig.system_prompt.variables.length > 0 ? (
              vmcpConfig.system_prompt.variables.map((variable, varIndex) => (
                <div key={`system-var-${varIndex}-${variable.name}`} className="rounded-lg p-3 border border-border">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex-1">
                      <span className="text-sm font-medium text-foreground">{variable.name}</span>
                      <div className="text-xs text-muted-foreground mt-1">
                        {variable.description || 'No description'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!isRemoteVMCP && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleEditVariable(varIndex)}
                            className="h-5 w-5 p-0"
                          >
                            <Edit className="h-3 w-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => removeVariable(varIndex)}
                            className="h-5 w-5 p-0 text-destructive"
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center">
                    <span className={`text-xs px-2 py-1 rounded ${
                      variable.required 
                        ? 'bg-amber-100 text-amber-800' 
                        : 'bg-green-100 text-green-800'
                    }`}>
                      {variable.required ? 'Required' : 'Optional'}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center text-sm py-4 text-muted-foreground italic">
                No parameters defined. Use param(parameter) syntax and click the + button to add them.
              </div>
            )}
          </div>
        </div>

        {/* Config Display */}
        <div className="bg-card p-2 rounded-2xl">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-medium underline underline-offset-4 decoration-accent text-foreground">Config</h4>
            <Button
              size="sm"
              variant="outline"
              onClick={handleAddNew}
              disabled={isRemoteVMCP}
              title={isRemoteVMCP ? 'Adding config variables disabled for remote vMCPs' : ''}
              className="h-6 w-6 p-0"
            >
              <Plus className="h-3 w-3" />
            </Button>
          </div>
          <div className="space-y-2">
            {vmcpConfig.environment_variables.length === 0 ? (
              <div className="text-center py-4 text-muted-foreground text-sm">
                <p className="mb-2">No config variables defined yet.</p>
                <p className="text-xs">Use config.CONFIG_VAR syntax in your content and click the + button to add them.</p>
              </div>
            ) : (
              vmcpConfig.environment_variables.map((envVar, varIndex) => (
                <div key={`all-env-${varIndex}-${envVar.name}`} className="bg-muted/20 rounded-lg p-2 border border-border/50">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-foreground font-mono">{envVar.name}</span>
                        {!isRemoteVMCP && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleEdit(varIndex)}
                            className="h-5 w-5 p-0"
                          >
                            <Edit className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {envVar.description || 'No description'}
                      </div>
                      <div className="text-xs text-foreground">
                        <span className="text-muted-foreground">Value: </span>
                        {envVar.value || <span className="text-muted-foreground italic">Not set</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-1 rounded ${
                        envVar.required 
                          ? 'bg-amber-100 text-amber-800' 
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {envVar.required ? 'Required' : 'Optional'}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
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
                  id="env-required"
                  checked={modalRequired}
                  onCheckedChange={(checked: boolean) => setModalRequired(checked)}
                />
                <Label htmlFor="env-required" className="text-sm font-medium">
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

      {/* Add/Edit Local Variable Modal */}
      {showVariableModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-lg">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              {editingVariableIndex !== null ? 'Edit Local Parameter' : 'Add Local Parameter'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Parameter Name
                </label>
                <Input
                  type="text"
                  value={variableModalName}
                  onChange={(e) => setVariableModalName(e.target.value)}
                  placeholder="PARAMETER_NAME"
                  className="font-mono"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Description
                </label>
                <Input
                  type="text"
                  value={variableModalDescription}
                  onChange={(e) => setVariableModalDescription(e.target.value)}
                  placeholder="What is this variable for?"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="var-required"
                  checked={variableModalRequired}
                  onCheckedChange={(checked: boolean) => setVariableModalRequired(checked)}
                />
                <Label htmlFor="var-required" className="text-sm font-medium">
                  Required
                </Label>
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button
                variant="outline"
                onClick={handleCancelVariable}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSaveVariable}
                disabled={!variableModalName.trim()}
                className="flex-1"
              >
                {editingVariableIndex !== null ? 'Update' : 'Add'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}