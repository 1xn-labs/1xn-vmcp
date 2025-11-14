
import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
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
  Lock,
  AlertTriangle,
  CheckCircle,
  ArrowLeft,
  MessageSquare,
  Info
} from 'lucide-react';
import VMCPDetailsDisplay from '@/components/vmcp/VMCPDetailsDisplay';
import { useToast } from '@/hooks/use-toast';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

interface VMCPData {
  id: string;
  name: string;
  description?: string;
  vmcp_config?: {
    selected_servers?: any[];
    selected_tools?: Record<string, string[]>;
    selected_resources?: Record<string, string[]>;
    selected_prompts?: Record<string, string[]>;
  };
  total_tools?: number;
  total_resources?: number;
  total_prompts?: number;
  environment_variables?: any[];
}

export default function VMCPOAuthSetupConfigurePage() {
  const router = useRouter();
  const params = useParams();
  const [searchParams] = useSearchParams();
  const { success, error: toastError } = useToast();
  
  const vmcpName = params.vmcp_name as string;
  const vmcpUsername = searchParams.get('vmcp_username');
  const authCode = searchParams.get('code');
  const state = searchParams.get('state');
  const redirectUrl = searchParams.get('redirect_url');
  const userId = searchParams.get('user_id');
  const vmcpType = searchParams.get('vmcp_type');
  const errorMessage = searchParams.get('error');
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [vmcpData, setVmcpData] = useState<VMCPData | null>(null);

  // Load VMCP data
  useEffect(() => {
    loadVMCPData();
  }, []);

  const loadVMCPData = async () => {
    try {
      setLoading(true);
      console.log('Loading VMCP data for:', vmcpName, vmcpUsername, userId, errorMessage);
      // If there's an error message, don't attempt to load VMCP data
      if (errorMessage) {
        setLoading(false);
        return;
      }

      // Check if we have a fetch_vmcp_config_from parameter
      const fetchConfigFrom = searchParams.get('fetch_vmcp_config_from');

      if (fetchConfigFrom) {
        // Use the new endpoint to fetch VMCP configuration
        const response = await fetch(fetchConfigFrom, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            original_state: state,
            vmcp_name: vmcpName,
            vmcp_username: vmcpUsername,
            user_id: userId,
          }),
        });

        if (response.ok) {
          const data = await response.json();
          // Transform the API response to match the expected frontend structure
          const vmcpConfig = data.vmcp_config || {};
          
          // Calculate totals from selected mappings
          const totalTools = Object.values(vmcpConfig.selected_tools || {}).reduce(
            (sum: number, tools: any) => sum + (Array.isArray(tools) ? tools.length : 0),
            0
          );
          const totalResources = Object.values(vmcpConfig.selected_resources || {}).reduce(
            (sum: number, resources: any) => sum + (Array.isArray(resources) ? resources.length : 0),
            0
          );
          // Calculate prompts: use backend total_prompts if available, otherwise count selected_prompts + custom_prompts
          const selectedPromptsCount = Object.values(vmcpConfig.selected_prompts || {}).reduce(
            (sum: number, prompts: any) => sum + (Array.isArray(prompts) ? prompts.length : 0),
            0
          );
          const customPromptsCount = Array.isArray(vmcpConfig.custom_prompts) ? vmcpConfig.custom_prompts.length : 0;
          const totalPrompts = vmcpConfig.total_prompts !== undefined 
            ? vmcpConfig.total_prompts 
            : selectedPromptsCount + customPromptsCount;
          
          // Extract name and description from VMCP config or first server
          const name = vmcpConfig.name || vmcpConfig.selected_servers?.[0]?.name || vmcpName;
          const description = vmcpConfig.description || vmcpConfig.selected_servers?.[0]?.description;
          
          // Transform to expected structure
          setVmcpData({
            id: data.vmcp_new_id || vmcpName,
            name: name,
            description: description,
            vmcp_config: vmcpConfig,
            total_tools: totalTools,
            total_resources: totalResources,
            total_prompts: totalPrompts,
            environment_variables: vmcpConfig.environment_variables || []
          });
        } else {
          throw new Error('Failed to fetch VMCP configuration');
        }
      } else {
        // Fallback to the original API call
        const response = await apiClient.getVMCPConfiguration(vmcpName, {
          code: authCode,
          state: state,
          redirect_url: redirectUrl,
          user_id: userId,
          vmcp_type: vmcpType,
        });

        if (response.success) {
          setVmcpData(response.data);
        } else {
          toastError('Failed to load VMCP data');
        }
      }
    } catch (error) {
      console.error('Error loading VMCP data:', error);
      toastError('Error loading VMCP data');
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteOAuth = async () => {
    try {
      setSaving(true);
      
      console.log('Saving VMCP Configuration');
      const response = await apiClient.saveVMCPConfiguration(vmcpName, {
        vmcp_config: vmcpData,
        code: authCode,
        state: state,
        user_id: userId,
        vmcp_type: vmcpType,
      });

      console.log('VMCP Configuration saved');

      // Simple OAuth completion - just redirect with the auth code
      if (redirectUrl) {
        console.log('Redirecting to:', redirectUrl);
        const separator = redirectUrl.includes('?') ? '&' : '?';
        // const finalUrl = redirectUrl + separator + 'code=' + authCode + (state ? '&state=' + state : '');
        const finalUrl = redirectUrl + (state ? '&state=' + state : '');
        window.location.href = finalUrl;
      } else {
        router.push(`/oauth_setup/${vmcpName}/callback?code=${authCode}&state=${state}&configured=true`);
      }
    } catch (error) {
      console.error('Error completing OAuth:', error);
      toastError('Error completing OAuth flow');
    } finally {
      setSaving(false);
    }
  };

  const handleReturnToClient = () => {
    if (redirectUrl) {
      const separator = redirectUrl.includes('?') ? '&' : '?';
      const finalUrl = redirectUrl + separator + 'error=' + encodeURIComponent(errorMessage || 'OAuth setup failed');
      console.log('Returning to client:', finalUrl);
      window.location.href = finalUrl;
    } else {
      router.push('/vmcp');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading OAuth configuration...</p>
        </div>
      </div>
    );
  }

  // Show error message if present
  if (errorMessage) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="h-12 w-12 rounded-xl bg-destructive/20 flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="h-6 w-6 text-destructive" />
          </div>
          <h1 className="text-2xl font-bold mb-4">OAuth Setup Error</h1>
          <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg mb-6">
            <p className="text-destructive text-sm">{errorMessage}</p>
          </div>
          <div className="flex gap-3 justify-center">
            {redirectUrl && (
              <Button
                onClick={handleReturnToClient}
                variant="destructive"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Return to Client
              </Button>
            )}
            
          </div>
        </div>
      </div>
    );
  }

  if (!vmcpData) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="text-center">
          <p className="text-destructive">OAuth configuration not found</p>
          <Button
            onClick={() => router.push('/vmcp')}
            className="mt-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to VMCP
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-12 w-12 rounded-xl bg-primary/20 flex items-center justify-center">
              <Container className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">
                Complete OAuth Setup
              </h1>
              <p className="text-muted-foreground">
                OAuth authentication for {vmcpData.name}
              </p>
            </div>
          </div>
        </div>

        {/* VMCP Information Card */}
        <Card className="mb-6">
          <CardHeader className="pb-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-xl">{vmcpData.name}</CardTitle>
                <CardDescription className="text-sm mt-1">
                  {vmcpData.description || 'No description available'}
                </CardDescription>
              </div>
              <Badge variant="default" className="text-xs px-2 py-1">
                {vmcpType === 'wellknown' ? 'Well-Known' : 'Public'}
              </Badge>
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
        <div className="mb-8">
          <VMCPDetailsDisplay 
            vmcpData={vmcpData}
            vmcpType={vmcpType || 'public'}
            isRemoteVMCP={false}
            showExpandableLists={false}
          />
        </div>

        {/* OAuth Notice */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-5 w-5 text-primary" />
              OAuth Setup Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                By completing the OAuth flow, you will:
              </p>
              <ul className="text-sm text-muted-foreground space-y-1 pl-4">
                <li>• Authenticate with the VMCP service</li>
                <li>• Grant necessary permissions for the VMCP to function</li>
                <li>• Complete the setup process</li>
              </ul>
              <p className="text-sm text-muted-foreground">
                You can configure server authentication and environment variables after OAuth completion.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Complete OAuth Button */}
        <div className="flex justify-center">
          <Button
            onClick={handleCompleteOAuth}
            disabled={saving}
            size="lg"
            className="px-8 py-3"
          >
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Completing OAuth...
              </>
            ) : (
              <>
                <CheckCircle className="h-4 w-4 mr-2" />
                Complete OAuth Setup
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
