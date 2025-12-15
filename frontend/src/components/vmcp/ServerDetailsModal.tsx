// components/vmcp/ServerDetailsModal.tsx

import { useState } from 'react';
import { Server, X, Wifi, WifiOff, Lock, LinkIcon, AlertTriangle, Activity, Terminal, Globe, CheckCircle, RefreshCw, Settings } from 'lucide-react';
import { PromptIcon, ToolIcon, ResourceIcon } from '@/lib/vmcp';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { McpServerInfo } from '@/api/generated/types.gen';
import { EnvironmentVariablesModal } from '@/components/vmcp/EnvironmentVariablesModal';
import { normalizeEnvVars } from '@/lib/app-utils';

interface ServerDetailsModalProps {
  server: McpServerInfo;
  isOpen: boolean;
  onClose: () => void;
  onRefresh: () => Promise<void>;
  onConnect: () => Promise<void>;
  onAuth: () => Promise<void>;
  onUpdateEnvVars?: (env: Record<string, string>) => Promise<void>;
  isLoading?: {
    refresh?: boolean;
    connect?: boolean;
    auth?: boolean;
    updateEnv?: boolean;
  };
}

export function ServerDetailsModal({
  server,
  isOpen,
  onClose,
  onRefresh,
  onConnect,
  onAuth,
  onUpdateEnvVars,
  isLoading = {}
}: ServerDetailsModalProps) {
  const [isWaitingForAuth, setIsWaitingForAuth] = useState(false);
  const [envVarsModalOpen, setEnvVarsModalOpen] = useState(false);

  const handleAuth = async () => {
    setIsWaitingForAuth(true);
    await onAuth();
  };

  if (!isOpen) return null;

  // Helper function to get status display
  const getModalStatusDisplay = (currentStatus: string | undefined) => {
    if (isLoading.refresh) {
      return {
        label: 'Fetching...',
        color: 'bg-blue-500/20 border-blue-500/30 text-blue-400',
        icon: Activity,
        bgColor: 'bg-blue-500/10'
      };
    }

    switch (currentStatus) {
      case 'connected':
        return {
          label: 'Connected',
          color: 'bg-green-500/20 border-green-500/30 text-green-400',
          icon: CheckCircle,
          bgColor: 'bg-green-500/10'
        };
      case 'auth_required':
        return {
          label: 'Auth Required',
          color: 'bg-amber-500/20 border-amber-500/30 text-amber-400',
          icon: Lock,
          bgColor: 'bg-amber-500/10'
        };
      case 'error':
        return {
          label: 'Error',
          color: 'bg-red-500/20 border-red-500/30 text-red-400',
          icon: AlertTriangle,
          bgColor: 'bg-red-500/10'
        };
      default:
        return {
          label: 'Disconnected',
          color: 'bg-gray-500/20 border-gray-500/30 text-gray-400',
          icon: WifiOff,
          bgColor: 'bg-gray-500/10'
        };
    }
  };

  // Helper function to get transport icon
  const getTransportIcon = (transport: string | undefined) => {
    switch (transport) {
      case 'stdio':
        return Terminal;
      case 'http':
        return Globe;
      case 'sse':
        return Wifi;
      default:
        return Server;
    }
  };



  const status = getModalStatusDisplay(server.status);
  const StatusIcon = status.icon;
  const TransportIcon = getTransportIcon(server.transport_type);

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-background border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
              <Server className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-foreground font-mono">{server.name}</h2>
              <div className="flex items-center gap-3 mt-1">
                <p className="text-sm text-muted-foreground">Server Details</p>
                <Badge
                  variant={server.status === 'connected' ? 'default' :
                    server.status === 'auth_required' ? 'secondary' :
                      server.status === 'error' ? 'destructive' : 'outline'}
                  className="text-xs"
                >
                  <StatusIcon className="h-3 w-3 mr-1" />
                  {status.label}
                </Badge>
              </div>
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
        {server.status === 'error' && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-3">
            <Activity className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div className="text-sm text-red-200">
              <p className="font-medium mb-1">{server.last_error}</p>
            </div>
          </div>
        )}

        {isWaitingForAuth && (
          <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-start gap-3">
            <Activity className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
            <div className="text-sm text-blue-200">
              <p className="font-medium mb-1">Authentication in progress</p>
              <p className="text-blue-200/80">
                Please complete the authentication process in the new window, then click the Refresh button to update the MCP status.
              </p>
            </div>
          </div>
        )}

        {/* Modal Content */}
        <div className="p-6 space-y-6">
          {/* Server Actions */}
          <div className="flex items-center justify-center">
            <div className="flex items-center gap-3">
              {/* Connect/Authorize Button */}
              {server.status === 'connected' ? (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isLoading.refresh || isLoading.connect || isLoading.auth}
                  className="flex items-center gap-2"
                >
                  <WifiOff className="h-4 w-4" />
                  Disconnect
                </Button>
              ) : server.status === 'auth_required' ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAuth}
                  disabled={isLoading.refresh || isLoading.connect || isLoading.auth || isWaitingForAuth}
                  className="flex items-center gap-2"
                >
                  <LinkIcon className="h-4 w-4" />
                  {isWaitingForAuth ? 'Waiting...' : 'Authorize'}
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onConnect}
                  disabled={isLoading.refresh || isLoading.connect || isLoading.auth}
                  className="flex items-center gap-2"
                >
                  <Wifi className="h-4 w-4" />
                  Connect
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={onRefresh}
                disabled={isLoading.refresh || isLoading.connect || isLoading.auth}
                className="flex items-center gap-2"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading.refresh ? 'animate-spin' : ''}`} />
                Refresh
              </Button>

              {/* Edit Environment Variables Button - only show for stdio servers */}
              {server.transport_type === 'stdio' && onUpdateEnvVars && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEnvVarsModalOpen(true)}
                  disabled={isLoading.refresh || isLoading.connect || isLoading.auth || isLoading.updateEnv}
                  className="flex items-center gap-2"
                >
                  <Settings className="h-4 w-4" />
                  Edit Env Vars
                </Button>
              )}
            </div>
          </div>

          {/* Server Description */}
          {server.description && (
            <div>
              <h3 className="text-sm font-medium text-foreground mb-2">Description</h3>
              <p className="text-sm text-muted-foreground">{server.description}</p>
            </div>
          )}

          {/* Connection Details */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-2">Connection Details</h3>
            <div className="flex gap-4">
              <div className="flex items-center gap-2">
                {/* <span className="text-sm text-muted-foreground">Transport:</span> */}
                <Badge variant="outline" className="text-xs">
                  <div className="flex items-center gap-1">
                    <TransportIcon className="h-3 w-3" />
                    {server.transport_type || 'unknown'}
                  </div>
                </Badge>
              </div>
              {server.url && (
                <div className="flex-1 items-start gap-2">
                  {/* <span className="text-sm text-muted-foreground shrink-0">URL:</span> */}
                  <code className="text-xs bg-muted px-2 py-1 rounded font-mono break-all">{server.url}</code>
                </div>
              )}
              {server.command && (
                <div className="flex-1 items-start gap-2">
                  {/* <span className="text-sm text-muted-foreground shrink-0">Command:</span> */}
                  <code className="text-xs bg-muted px-2 py-1 rounded font-mono break-all"># {server.command} {server.args ? ' ' + server.args.join(' ') : ''}</code>
                </div>
              )}
            </div>
          </div>

          {/* Environment Variables - only show for stdio servers */}
          {server.transport_type === 'stdio' && (server.env || (server as any).env_vars) && (
            <div>
              <h3 className="text-sm font-medium text-foreground mb-2">Environment Variables</h3>
              <div className="space-y-1">
                {(() => {
                  const serverAny = server as any;
                  const envVars = server.env || (serverAny.env_vars && typeof serverAny.env_vars === 'object' ? serverAny.env_vars : {});
                  if (!envVars || typeof envVars !== 'object' || Object.keys(envVars).length === 0) {
                    return <p className="text-sm text-muted-foreground">No environment variables configured</p>;
                  }
                  return Object.entries(envVars).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 text-xs">
                      <code className="bg-muted px-2 py-1 rounded font-mono text-foreground/80">{key}</code>
                      <span className="text-muted-foreground">=</span>
                      <code className="bg-muted px-2 py-1 rounded font-mono text-muted-foreground">
                        {String(value).length > 50 ? `${String(value).substring(0, 50)}...` : String(value)}
                      </code>
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}

          {/* Capabilities Summary */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3">Capabilities</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <CardContent className="p-4 text-center">
                  <div className="flex items-center justify-center mb-2">
                    <ToolIcon className="h-8 w-8 text-primary" />
                  </div>
                  <div className="text-2xl font-bold text-foreground">
                    {(server.tool_details?.length || 0)}
                  </div>
                  <div className="text-sm text-muted-foreground">Tools Available</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 text-center">
                  <div className="flex items-center justify-center mb-2">
                    <PromptIcon className="h-8 w-8 text-primary" />
                  </div>
                  <div className="text-2xl font-bold text-foreground">
                    {(server.prompt_details?.length || 0)}
                  </div>
                  <div className="text-sm text-muted-foreground">Prompts Available</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 text-center">
                  <div className="flex items-center justify-center mb-2">
                    <ResourceIcon className="h-8 w-8 text-primary" />
                  </div>
                  <div className="text-2xl font-bold text-foreground">
                    {(server.resource_details?.length || 0)}
                  </div>
                  <div className="text-sm text-muted-foreground">Resources Available</div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Last Error Info */}
          {server.last_error && (
            <div className="text-center py-4 border-t border-border">
              <p className="text-sm text-red-400">
                Error: {server.last_error}
              </p>
            </div>
          )}

          {/* Last Connected Info */}
          {server.last_connected && (
            <div className="text-center py-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                Last connected: {new Date(server.last_connected).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Environment Variables Modal */}
      {onUpdateEnvVars && (
        <EnvironmentVariablesModal
          isOpen={envVarsModalOpen}
          onClose={() => setEnvVarsModalOpen(false)}
          onSubmit={async (env) => {
            await onUpdateEnvVars(env);
            setEnvVarsModalOpen(false);
          }}
          initialEnvVars={server.env || (server as any).env_vars}
          serverName={server.name}
          isLoading={isLoading.updateEnv}
        />
      )}
    </div>
  );
}
