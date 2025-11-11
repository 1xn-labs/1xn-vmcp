
import React, { useState } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { 
  ArrowLeft,
  Plus,
  Server as ServerIcon,
  Terminal,
  Globe,
  Wifi,
  Settings,
  AlertTriangle,
  CheckCircle,
  RefreshCw
} from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
import { useToast } from '@/hooks/use-toast';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

interface ServerFormData {
  name: string;
  description: string;
  transport: 'stdio' | 'http' | 'sse';
  command: string;
  url: string;
  args: string;
  env: string;
  headers: string;
  auto_connect: boolean;
  enabled: boolean;
}

export default function AddServerPage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const { success, error: toastError } = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [formData, setFormData] = useState<ServerFormData>({
    name: '',
    description: '',
    transport: 'stdio',
    command: '',
    url: '',
    args: '',
    env: '',
    headers: '',
    auto_connect: false,
    enabled: true
  });

  React.useEffect(() => {
    // Redirect to login if not authenticated and not loading
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
      return;
    }
  }, [authLoading, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('Server name is required');
      return;
    }

    if (formData.transport === 'stdio' && !formData.command.trim()) {
      setError('Command is required for STDIO transport');
      return;
    }

    if ((formData.transport === 'http' || formData.transport === 'sse') && !formData.url.trim()) {
      setError('URL is required for HTTP/SSE transport');
      return;
    }

    // Validate JSON fields
    if (formData.env.trim() && formData.env !== '{}') {
      try {
        JSON.parse(formData.env);
      } catch {
        setError('Environment variables must be valid JSON (e.g., {"KEY": "value"})');
        return;
      }
    }

    if (formData.headers.trim() && formData.headers !== '{}') {
      try {
        JSON.parse(formData.headers);
      } catch {
        setError('Headers must be valid JSON (e.g., {"Authorization": "Bearer token"})');
        return;
      }
    }

    setLoading(true);
    setError(null);

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }
      
      // Prepare the server data for new API
      const serverData = {
        name: formData.name,
        mode: formData.transport,
        description: formData.description,
        command: formData.transport === 'stdio' ? formData.command : undefined,
        args: formData.args ? formData.args.split(',').map(arg => arg.trim()) : undefined,
        env: formData.env ? JSON.parse(formData.env) : undefined,
        url: (formData.transport === 'http' || formData.transport === 'sse') ? formData.url : undefined,
        headers: formData.headers ? JSON.parse(formData.headers) : undefined,
        auto_connect: formData.auto_connect,
        enabled: formData.enabled
      };
      
      const result = await apiClient.installMCPServer(serverData, accessToken);
      
      if (result.success) {
        console.log('✅ Server added successfully:', result.data);
        success('Server added successfully!');
        // Redirect back to servers page
        router.push('/servers?success=added');
      } else {
        throw new Error(result.error || 'Failed to add server');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to add server';
      setError(errorMessage);
      toastError(errorMessage);
      console.error('Error adding server:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (field: keyof ServerFormData, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const getTransportIcon = (transport: string) => {
    switch (transport) {
      case 'stdio':
        return Terminal;
      case 'http':
        return Globe;
      case 'sse':
        return Wifi;
      default:
        return ServerIcon;
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const TransportIcon = getTransportIcon(formData.transport);

  return (
    <div className="min-h-screen bg-background">
      {/* Main Content */}
      <div className="h-screen overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-4 mb-6">
              <Button
                variant="ghost"
                onClick={() => router.push('/servers')}
                className="text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Servers
              </Button>
            </div>
            
            <div className="flex items-center gap-3 mb-2">
              <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <Plus className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-foreground">Add MCP Server</h1>
                <p className="text-muted-foreground">Configure a new Model Context Protocol server connection</p>
              </div>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <Card className="hover:shadow-lg transition-shadow">
              <CardContent className="p-8">
              {/* Basic Information */}
              <div className="mb-8">
                <div className="flex items-center gap-2 mb-6">
                  <Settings className="h-5 w-5 text-primary" />
                  <h3 className="text-xl font-semibold text-foreground">Basic Information</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-2">
                      Server Name <span className="text-destructive">*</span>
                    </label>
                    <Input
                      type="text"
                      value={formData.name}
                      onChange={(e) => handleFieldChange('name', e.target.value)}
                      placeholder="my-mcp-server"
                      required
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      Unique identifier for this server
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-foreground mb-2">
                      Transport Type <span className="text-destructive">*</span>
                    </label>
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { value: 'stdio', label: 'STDIO', icon: Terminal, desc: 'Command line process' },
                        { value: 'http', label: 'HTTP', icon: Globe, desc: 'HTTP endpoint' },
                        { value: 'sse', label: 'SSE', icon: Wifi, desc: 'Server-sent events' }
                      ].map((option) => {
                        const Icon = option.icon;
                        return (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => handleFieldChange('transport', option.value as 'stdio' | 'http' | 'sse')}
                            className={`p-4 rounded-lg border-2 text-center transition-all ${
                              formData.transport === option.value
                                ? 'border-primary bg-primary/10 text-primary'
                                : 'border-border hover:border-primary/50 text-muted-foreground hover:text-foreground'
                            }`}
                          >
                            <Icon className="h-6 w-6 mx-auto mb-2" />
                            <div className="font-medium text-sm">{option.label}</div>
                            <div className="text-xs opacity-75">{option.desc}</div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                <div className="mt-6">
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Description
                  </label>
                  <Textarea
                    value={formData.description}
                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => handleFieldChange('description', e.target.value)}
                    placeholder="Brief description of this server"
                    rows={3}
                  />
                </div>
              </div>

              {/* STDIO Configuration */}
              {formData.transport === 'stdio' && (
                <div className="mb-8 pt-8">
                  <Separator className="mb-6" />
                  <div className="flex items-center gap-2 mb-6">
                    <Terminal className="h-5 w-5 text-orange-600 dark:text-orange-400" />
                    <h3 className="text-xl font-semibold text-foreground">STDIO Configuration</h3>
                  </div>

                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        Command <span className="text-destructive">*</span>
                      </label>
                      <Input
                        type="text"
                        value={formData.command}
                        onChange={(e) => handleFieldChange('command', e.target.value)}
                        placeholder="python -m mcp_server"
                        required
                      />
                      <p className="mt-1 text-xs text-muted-foreground">
                        Command to execute the MCP server
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        Arguments
                      </label>
                      <Input
                        type="text"
                        value={formData.args}
                        onChange={(e) => handleFieldChange('args', e.target.value)}
                        placeholder='["--config", "config.json"] or --config config.json'
                      />
                      <p className="mt-1 text-xs text-muted-foreground">
                        Command line arguments (JSON array or space-separated)
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        Environment Variables
                      </label>
                      <Textarea
                        value={formData.env}
                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => handleFieldChange('env', e.target.value)}
                        placeholder='{"API_KEY": "your-key", "DEBUG": "true"}'
                        rows={3}
                      />
                      <p className="mt-1 text-xs text-muted-foreground">
                        Environment variables as JSON object
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* HTTP/SSE Configuration */}
              {(formData.transport === 'http' || formData.transport === 'sse') && (
                <div className="mb-8 pt-8">
                  <Separator className="mb-6" />
                  <div className="flex items-center gap-2 mb-6">
                    <TransportIcon className="h-5 w-5 text-green-600 dark:text-green-400" />
                    <h3 className="text-xl font-semibold text-foreground">{formData.transport.toUpperCase()} Configuration</h3>
                  </div>

                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        Server URL <span className="text-destructive">*</span>
                      </label>
                      <Input
                        type="url"
                        value={formData.url}
                        onChange={(e) => handleFieldChange('url', e.target.value)}
                        placeholder="https://api.example.com/mcp"
                        required
                      />
                      <p className="mt-1 text-xs text-muted-foreground">
                        Full URL to the MCP server endpoint
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-2">
                        HTTP Headers
                      </label>
                      <Textarea
                        value={formData.headers}
                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => handleFieldChange('headers', e.target.value)}
                        placeholder='{"User-Agent": "MCP-Client", "Accept": "application/json"}'
                        rows={3}
                      />
                      <p className="mt-1 text-xs text-muted-foreground">
                        Custom HTTP headers as JSON object
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Connection Options */}
              <div className="pt-8">
                <Separator className="mb-6" />
                <div className="flex items-center gap-2 mb-6">
                  <CheckCircle className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  <h3 className="text-xl font-semibold text-foreground">Connection Options</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="auto_connect"
                      checked={formData.auto_connect}
                      onChange={(e) => handleFieldChange('auto_connect', e.target.checked)}
                      className="w-4 h-4 text-primary bg-background border-border rounded focus:ring-primary focus:ring-2"
                    />
                    <label htmlFor="auto_connect" className="ml-3 text-sm text-foreground">
                      Auto-connect on startup
                    </label>
                  </div>

                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="enabled"
                      checked={formData.enabled}
                      onChange={(e) => handleFieldChange('enabled', e.target.checked)}
                      className="w-4 h-4 text-primary bg-background border-border rounded focus:ring-primary focus:ring-2"
                    />
                    <label htmlFor="enabled" className="ml-3 text-sm text-foreground">
                      Enabled
                    </label>
                  </div>
                </div>
              </div>
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex gap-4 justify-end mt-8 pb-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push('/servers')}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Adding Server...
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Server
                  </>
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
} 