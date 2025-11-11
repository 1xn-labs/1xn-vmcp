
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Container, 
  Server, 
  Zap, 
  Download, 
  Globe,
  Share2,
  ExternalLink,
  Copy,
  CheckCircle
} from 'lucide-react';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';

export default function VMCPSharePage() {
  const params = useParams();
  const router = useRouter();
  const { success, error: toastError } = useToast();
  
  const [vmcpId, setVmcpId] = useState<string>('');
  const [sharedVMCP, setSharedVMCP] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (params.vmcp_id) {
      setVmcpId(params.vmcp_id as string);
      loadSharedVMCP(params.vmcp_id as string);
    }
  }, [params.vmcp_id]);

  const loadSharedVMCP = async (id: string) => {
    try {
      setLoading(true);
      const accessToken = localStorage.getItem('access_token');
      
      // Try to get as public vMCP first
      if (accessToken) {
        try {
          const response = await apiClient.getPublicVMCPDetails(id, accessToken);
          if (response.success && response.data) {
            setSharedVMCP(response.data);
            return;
          }
        } catch (error) {
          console.log('Not a public vMCP, trying to get as shared');
        }
      }

      // If not public, try to get as shared vMCP
      // For now, we'll show a placeholder since the backend endpoint might not exist yet
      setSharedVMCP({
        id: id,
        name: 'Shared vMCP',
        description: 'This vMCP has been shared with you',
        creator_username: 'Unknown',
        install_count: 0,
        total_tools: 0,
        total_resources: 0,
        total_prompts: 0,
        tags: ['shared'],
        vmcp_config: {
          selected_servers: [],
          selected_tools: {},
          selected_resources: {},
          selected_prompts: {}
        }
      });

    } catch (error) {
      toastError('Failed to load shared vMCP');
      router.push('/vmcp');
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = () => {
    router.push(`/vmcp/install/${vmcpId}`);
  };

  const copyShareUrl = async () => {
    try {
      const shareUrl = window.location.href;
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      success('Share URL copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toastError('Failed to copy share URL');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading shared vMCP...</p>
        </div>
      </div>
    );
  }

  if (!sharedVMCP) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <p className="text-destructive">vMCP not found or access denied</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen text-foreground bg-background">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center">
              <Container className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold">Shared vMCP</h1>
              <p className="text-muted-foreground">View and install {sharedVMCP.name}</p>
            </div>
          </div>
        </div>

        {/* Main vMCP Card */}
        <Card className="mb-8">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="h-16 w-16 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center">
                  <Container className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-2xl">{sharedVMCP.name}</CardTitle>
                  <CardDescription className="text-lg mt-2">
                    {sharedVMCP.description || 'No description available'}
                  </CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-sm">
                  <Globe className="h-3 w-3 mr-1" />
                  Shared
                </Badge>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyShareUrl}
                  className="flex items-center gap-2"
                >
                  {copied ? (
                    <>
                      <CheckCircle className="h-4 w-4" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      Copy URL
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <Server className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <div className="text-2xl font-bold">
                  {sharedVMCP.vmcp_config?.selected_servers?.length || 0}
                </div>
                <div className="text-sm text-muted-foreground">Servers</div>
              </div>
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <Zap className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <div className="text-2xl font-bold">{sharedVMCP.total_tools || 0}</div>
                <div className="text-sm text-muted-foreground">Tools</div>
              </div>
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <Container className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <div className="text-2xl font-bold">{sharedVMCP.total_resources || 0}</div>
                <div className="text-sm text-muted-foreground">Resources</div>
              </div>
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <Download className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <div className="text-2xl font-bold">{sharedVMCP.install_count || 0}</div>
                <div className="text-sm text-muted-foreground">Installs</div>
              </div>
            </div>

            {/* Creator Info */}
            <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
              <div>
                <p className="text-sm text-muted-foreground">Shared by</p>
                <p className="font-medium">{sharedVMCP.creator_username || 'Unknown'}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tags */}
        {sharedVMCP.tags && sharedVMCP.tags.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Tags</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {sharedVMCP.tags.map((tag: string, index: number) => (
                  <Badge key={index} variant="outline" className="text-sm">
                    {tag}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Server Details */}
        {sharedVMCP.vmcp_config?.selected_servers && sharedVMCP.vmcp_config.selected_servers.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                Included Servers
              </CardTitle>
              <CardDescription>
                MCP servers that will be installed with this vMCP
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sharedVMCP.vmcp_config.selected_servers.map((server: any, index: number) => (
                  <div key={index} className="p-4 border rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-lg bg-muted/50 flex items-center justify-center">
                        <Server className="h-5 w-5 text-muted-foreground" />
                      </div>
                      <div>
                        <h4 className="font-medium">{server.name}</h4>
                        <p className="text-sm text-muted-foreground">
                          {server.description || 'No description available'}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Installation Instructions */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Installation Instructions</CardTitle>
            <CardDescription>
              Follow these steps to install this vMCP to your account
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="h-6 w-6 rounded-full bg-primary/20 text-primary text-sm font-medium flex items-center justify-center flex-shrink-0 mt-0.5">
                  1
                </div>
                <div>
                  <h4 className="font-medium">Click Install</h4>
                  <p className="text-sm text-muted-foreground">
                    Click the "Install vMCP" button above to start the installation process
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="h-6 w-6 rounded-full bg-primary/20 text-primary text-sm font-medium flex items-center justify-center flex-shrink-0 mt-0.5">
                  2
                </div>
                <div>
                  <h4 className="font-medium">Resolve Conflicts</h4>
                  <p className="text-sm text-muted-foreground">
                    Review and resolve any server naming conflicts with your existing setup
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="h-6 w-6 rounded-full bg-primary/20 text-primary text-sm font-medium flex items-center justify-center flex-shrink-0 mt-0.5">
                  3
                </div>
                <div>
                  <h4 className="font-medium">Complete Installation</h4>
                  <p className="text-sm text-muted-foreground">
                    The vMCP will be installed and available in your account
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex gap-4 justify-center">
          <Button
            variant="outline"
            onClick={() => router.push('/vmcp')}
            size="lg"
          >
            Back to vMCPs
          </Button>
          <Button
            onClick={handleInstall}
            size="lg"
            className="flex items-center gap-2"
          >
            <Download className="h-5 w-5" />
            Install vMCP
          </Button>
        </div>
      </div>
    </div>
  );
}
