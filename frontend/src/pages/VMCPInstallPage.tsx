
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
  Loader2, 
  Link as LinkIcon,
  MessageSquare,
  GitFork,
  Info
} from 'lucide-react';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/auth-context';
import { FaviconIcon } from '@/components/ui/favicon-icon';
import VMCPDetailsDisplay from '@/components/vmcp/VMCPDetailsDisplay';

export default function VMCPInstallPage() {
  const params = useParams();
  const router = useRouter();
  const { success, error: toastError } = useToast();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  
  const [vmcpId, setVmcpId] = useState<string>('');
  const [vmcpType, setVmcpType] = useState<string>('public');
  const [vmcpData, setVmcpData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);


  // Helper function to detect if icon is URL or base64
  const isIconUrl = (icon: string) => {
    return icon.startsWith('http://') || icon.startsWith('https://');
  };

  // Helper function to get icon source
  const getIconSource = (vmcp: any) => {
    if (vmcp.metadata?.icon) {
      return isIconUrl(vmcp.metadata.icon) 
        ? vmcp.metadata.icon 
        : `data:image/png;base64,${vmcp.metadata.icon}`;
    }
    return null;
  };

  useEffect(() => {
    // Redirect to login if not authenticated and not loading
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
      return;
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (params.vmcp_id && params.vmcp_type) {
      setVmcpId(params.vmcp_id as string);
      setVmcpType(params.vmcp_type as string);
      loadVMCPData(params.vmcp_id as string, params.vmcp_type as string);
    }
  }, [params.vmcp_id, params.vmcp_type]);

  const loadVMCPData = async (id: string, type: string) => {
    try {
      setLoading(true);
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to install vMCPs');
        router.push('/login');
        return;
      }

      let response;
      response = await apiClient.getPublicVMCPDetails(id, accessToken);

      if (response.success && response.data) {
        setVmcpData(response.data);
      } else {
        toastError(`Failed to load ${type} vMCP details`);
        router.push('/vmcp');
      }
    } catch (error) {
      toastError('Failed to load vMCP details');
      router.push('/vmcp');
    } finally {
      setLoading(false);
    }
  };

  const installVMCP = async () => {
    try {
      setInstalling(true);
      console.log('🔧 vmcpData:', vmcpData);
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        toastError('Please log in to install vMCPs');
        router.push('/login');
        return;
      }
      console.log('🔧 setting up installVMCP:', accessToken);

      // Send the VMCPConfig directly as-is, just add remote tag
      const vmcpConfig = {
        ...vmcpData,
        user_id: user?.id || '',
        // is_public: false, // Always install as private
        // is_wellknown: vmcpType === 'wellknown', // Mark if it's from well-known
        // upstream_id: vmcpData.id, // Track the upstream ID
        // upstream_type: vmcpType, // Track the upstream type
        // tags: [...(vmcpData.tags || []), 'remote'] // Add remote tag
      };

      console.log('🔧 Calling installVMCP with vmcpId:', vmcpId);
      const result = await apiClient.installVMCP(vmcpId, accessToken);
      console.log('🔧 installVMCP result:', result);
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to install vMCP');
      }

      success('vMCP installed successfully!');
      
      // Redirect to vMCP page
      router.push('/vmcp');
      
    } catch (error) {
      console.error('❌ Error installing vMCP:', error);
      toastError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setInstalling(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading vMCP details...</p>
        </div>
      </div>
    );
  }

  if (!vmcpData) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <p className="text-destructive">vMCP not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center relative overflow-hidden">
              {getIconSource(vmcpData) ? (
                <img
                  src={getIconSource(vmcpData)} 
                  alt={`${vmcpData.name} icon`}
                  className="h-7 w-7 object-contain"
                />
              ) : (
                <Container className="h-5 w-5 text-primary" />
              )}
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold mb-1">
                Install {vmcpType === 'wellknown' ? 'Well-Known' : 'Public'} vMCP
              </h1>
              <p className="text-sm text-muted-foreground">
                Review and install {vmcpData.name} to your account
              </p>
            </div>
          </div>
        </div>

        {/* vMCP Overview Card */}
        <Card className="mb-6">
          <CardHeader className="pb-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-xl">{vmcpData.name}</CardTitle>
                <CardDescription className="text-sm mt-1">
                  {vmcpData.description || 'No description available'}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Servers */}
              <div className="text-center p-4 rounded-lg bg-muted/30">
                <Server className="h-6 w-6 mx-auto mb-2 text-primary" />
                <div className="text-xl font-bold">{vmcpData.vmcp_config?.selected_servers?.length || 0}</div>
                <div className="text-xs text-muted-foreground">MCP Servers</div>
              </div>
              
              {/* Tools */}
              <div className="text-center p-4 rounded-lg bg-muted/30">
                <Zap className="h-6 w-6 mx-auto mb-2 text-primary" />
                <div className="text-xl font-bold">{vmcpData.total_tools || 0}</div>
                <div className="text-xs text-muted-foreground">Tools</div>
              </div>
              
              {/* Resources */}
              <div className="text-center p-4 rounded-lg bg-muted/30">
                <LinkIcon className="h-6 w-6 mx-auto mb-2 text-primary" />
                <div className="text-xl font-bold">{vmcpData.total_resources || 0}</div>
                <div className="text-xs text-muted-foreground">Resources</div>
              </div>
              
              {/* Prompts */}
              <div className="text-center p-4 rounded-lg bg-muted/30">
                <MessageSquare className="h-6 w-6 mx-auto mb-2 text-primary" />
                <div className="text-xl font-bold">{vmcpData.total_prompts || 0}</div>
                <div className="text-xs text-muted-foreground">Prompts</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Detailed Information */}
        <VMCPDetailsDisplay 
          vmcpData={vmcpData}
          vmcpType={vmcpType}
          isRemoteVMCP={false}
          showExpandableLists={true}
        />



        {/* Information Section */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-5 w-5 text-blue-500" />
              Installation Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                This vMCP will be installed as a <strong>read-only copy</strong>. After installation, you will only be able to edit:
              </p>
              <ul className="text-sm text-muted-foreground space-y-1 ml-4">
                <li>• Server authentication settings in the MCP Servers tab</li>
                <li>• Environment variable values</li>
              </ul>
              <p className="text-sm text-muted-foreground">
                To make a fully editable copy, you can fork this vMCP after installation.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex justify-center gap-4 mt-8">
          <Button
            onClick={installVMCP}
            disabled={installing}
            size="lg"
            className="px-8 py-3"
          >
            {installing ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Installing...
              </>
            ) : (
              <>
                <Download className="h-4 w-4 mr-2" />
                Install vMCP
              </>
            )}
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="px-8 py-3"
            disabled
            title="Fork functionality coming soon"
          >
            <GitFork className="h-4 w-4 mr-2" />
            Fork vMCP
          </Button>
        </div>

      </div>
    </div>
  );
}
