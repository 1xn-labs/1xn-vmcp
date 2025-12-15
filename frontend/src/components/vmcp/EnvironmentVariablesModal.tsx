// components/vmcp/EnvironmentVariablesModal.tsx

import React from 'react';
import { X, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { KeyValueInput } from '@/components/ui/key-value-input';

export interface EnvironmentVariablesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (env: Record<string, string>) => Promise<void>;
  initialEnvVars?: Record<string, string> | string | null;
  serverName?: string;
  isLoading?: boolean;
}

export function EnvironmentVariablesModal({
  isOpen,
  onClose,
  onSubmit,
  initialEnvVars,
  serverName,
  isLoading = false
}: EnvironmentVariablesModalProps) {
  if (!isOpen) return null;

  // Convert initial env_vars to array format for KeyValueInput
  const convertEnvVarsToArray = (envVars: Record<string, string> | string | null | undefined): Array<{key: string, value: string}> => {
    if (!envVars) return [];
    
    // If it's a string, parse it
    if (typeof envVars === 'string') {
      const parsed: Array<{key: string, value: string}> = [];
      const lines = envVars.split('\n');
      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine && !trimmedLine.startsWith('#')) {
          const equalIndex = trimmedLine.indexOf('=');
          if (equalIndex > 0) {
            const key = trimmedLine.substring(0, equalIndex).trim();
            const value = trimmedLine.substring(equalIndex + 1).trim();
            parsed.push({ key, value });
          }
        }
      }
      return parsed;
    }
    
    // If it's an object, convert to array
    if (typeof envVars === 'object') {
      return Object.entries(envVars).map(([key, value]) => ({
        key,
        value: String(value)
      }));
    }
    
    return [];
  };

  // Convert array format back to dict
  const convertArrayToEnv = (pairs: Array<{key: string, value: string}>): Record<string, string> => {
    const env: Record<string, string> = {};
    for (const pair of pairs) {
      if (pair.key.trim()) {
        env[pair.key.trim()] = pair.value.trim();
      }
    }
    return env;
  };

  const [envPairs, setEnvPairs] = React.useState<Array<{key: string, value: string}>>(
    () => convertEnvVarsToArray(initialEnvVars)
  );

  // Update when initialEnvVars changes
  React.useEffect(() => {
    setEnvPairs(convertEnvVarsToArray(initialEnvVars));
  }, [initialEnvVars]);

  const handleSubmit = async () => {
    const env = convertArrayToEnv(envPairs);
    await onSubmit(env);
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-background border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-linear-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
              <RefreshCw className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-foreground">
                Configure Environment Variables
              </h2>
              <p className="text-sm text-muted-foreground">
                {serverName ? `Set environment variables for ${serverName}` : 'Set environment variables for this server'}
              </p>
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
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Configure the environment variables required by this server. These will be passed to the server process when it starts.
            </p>
          </div>

          <KeyValueInput
            label="Environment Variables"
            placeholder="Add environment variables"
            keyPlaceholder="Variable name (e.g., OPENAI_API_KEY)"
            valuePlaceholder="Variable value"
            pairs={envPairs}
            onChange={setEnvPairs}
          />

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
              onClick={handleSubmit}
              disabled={isLoading}
              className="flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Installing...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4" />
                  Install Server
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
