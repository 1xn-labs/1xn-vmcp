
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { Button } from '@/components/ui/button';
// Card components - inline definitions to avoid import issues
const Card = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={`rounded-lg border bg-white/10 backdrop-blur-lg border-white/20 shadow-sm ${className || ''}`} {...props}>
    {children}
  </div>
);

const CardHeader = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={`flex flex-col space-y-1.5 p-6 ${className || ''}`} {...props}>
    {children}
  </div>
);

const CardTitle = ({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
  <h3 className={`text-2xl font-semibold leading-none tracking-tight text-white ${className || ''}`} {...props}>
    {children}
  </h3>
);

const CardDescription = ({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
  <p className={`text-sm text-gray-300 ${className || ''}`} {...props}>
    {children}
  </p>
);

const CardContent = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={`p-6 pt-0 ${className || ''}`} {...props}>
    {children}
  </div>
);
import { ExternalLink, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

interface AuthorizationData {
  authorization_url: string;
  state: string;
  message: string;
  instructions: string;
}

export default function OAuthAuthorizePage() {
  const router = useRouter();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const [authData, setAuthData] = useState<AuthorizationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<'pending' | 'success' | 'error'>('pending');

  const serverName = searchParams.get('server_name');
  const returnUrl = searchParams.get('return_url') || '/servers';

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }

    if (!serverName) {
      setError('Server name is required');
      setLoading(false);
      return;
    }

    initiateAuthorization();
  }, [isAuthenticated, serverName, router]);

  const initiateAuthorization = async () => {
    try {
      setLoading(true);
      setError(null);

      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const result = await apiClient.initiateMCPServerAuth(serverName!, accessToken);
      
      if (result.success && result.data) {
        setAuthData(result.data);
        setAuthStatus('pending');
      } else {
        throw new Error(result.error || 'Failed to initiate authorization');
      }
    } catch (err) {
      console.error('Authorization initiation error:', err);
      setError(err instanceof Error ? err.message : 'Failed to initiate authorization');
      setAuthStatus('error');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAuthorizationUrl = () => {
    if (authData?.authorization_url) {
      window.open(authData.authorization_url, '_blank');
    }
  };

  const handleCompleteAuthorization = async () => {
    try {
      setLoading(true);
      
      // Wait a moment for the OAuth callback to complete
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Check if authorization was successful by refreshing server status
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      // Try to connect the server to verify authorization
      const connectResult = await apiClient.connectMCPServer(serverName!, accessToken);
      
      if (connectResult.success) {
        setAuthStatus('success');
        // Redirect back to servers page after a short delay
        setTimeout(() => {
          router.push(returnUrl);
        }, 2000);
      } else {
        // If connect fails, check if the server status has changed to connected
        // by refreshing the server list
        const serversResult = await apiClient.listMCPServers(accessToken);
        if (serversResult.success && serversResult.data) {
          const responseData = serversResult.data as any;
          const servers = responseData.servers || serversResult.data;
          const server = servers.find((s: any) => s.name === serverName);
          if (server && server.status === 'connected') {
            setAuthStatus('success');
            setTimeout(() => {
              router.push(returnUrl);
            }, 2000);
            return;
          }
        }
        
        setAuthStatus('error');
        setError('Authorization may not have completed successfully. Please try again.');
      }
    } catch (err) {
      console.error('Authorization completion error:', err);
      setAuthStatus('error');
      setError('Failed to verify authorization completion');
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = () => {
    setError(null);
    setAuthStatus('pending');
    initiateAuthorization();
  };

  const handleCancel = () => {
    router.push(returnUrl);
  };

  if (loading && !authData) {
    return (
      <div className="min-h-screen bg-linear-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-white/10 backdrop-blur-lg border-white/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-center space-x-2">
              <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
              <span className="text-white">Initializing authorization...</span>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error && !authData) {
    return (
      <div className="min-h-screen bg-linear-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-white/10 backdrop-blur-lg border-white/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center space-x-2">
              <XCircle className="h-6 w-6 text-red-400" />
              <span>Authorization Error</span>
            </CardTitle>
            <CardDescription className="text-red-200">
              {error}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex space-x-2">
              <Button onClick={handleRetry} className="flex-1">
                Retry
              </Button>
              <Button onClick={handleCancel} variant="outline" className="flex-1">
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <Card className="w-full max-w-lg bg-white/10 backdrop-blur-lg border-white/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center space-x-2">
            {authStatus === 'success' && <CheckCircle className="h-6 w-6 text-green-400" />}
            {authStatus === 'error' && <XCircle className="h-6 w-6 text-red-400" />}
            {authStatus === 'pending' && <Loader2 className="h-6 w-6 animate-spin text-blue-400" />}
            <span>
              {authStatus === 'success' && 'Authorization Successful'}
              {authStatus === 'error' && 'Authorization Failed'}
              {authStatus === 'pending' && `Authorize ${serverName}`}
            </span>
          </CardTitle>
          <CardDescription className="text-gray-300">
            {authData?.message || 'Complete the authorization process'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {authStatus === 'pending' && authData && (
            <>
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                <p className="text-blue-200 text-sm mb-3">
                  {authData.instructions}
                </p>
                <div className="bg-black/20 rounded p-3">
                  <p className="text-xs text-gray-400 mb-1">Authorization URL:</p>
                  <p className="text-xs text-blue-300 break-all">
                    {authData.authorization_url}
                  </p>
                </div>
              </div>
              
              <div className="space-y-3">
                <Button 
                  onClick={handleOpenAuthorizationUrl}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open Authorization Page
                </Button>
                
                <div className="text-center">
                  <p className="text-sm text-gray-400 mb-2">
                    After completing authorization in the new window, click the button below:
                  </p>
                  <Button 
                    onClick={handleCompleteAuthorization}
                    disabled={loading}
                    variant="outline"
                    className="w-full"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Verifying Authorization...
                      </>
                    ) : (
                      'Complete Authorization'
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}

          {authStatus === 'success' && (
            <div className="text-center space-y-4">
              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4">
                <p className="text-green-200">
                  Authorization completed successfully! Redirecting back to servers...
                </p>
              </div>
              <Button onClick={() => router.push(returnUrl)} className="w-full">
                Go to Servers
              </Button>
            </div>
          )}

          {authStatus === 'error' && (
            <div className="space-y-4">
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                <p className="text-red-200">
                  {error || 'Authorization failed. Please try again.'}
                </p>
              </div>
              <div className="flex space-x-2">
                <Button onClick={handleRetry} className="flex-1">
                  Retry
                </Button>
                <Button onClick={handleCancel} variant="outline" className="flex-1">
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
} 