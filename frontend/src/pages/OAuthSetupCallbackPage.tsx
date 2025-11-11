
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';

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

import { Button } from '@/components/ui/button';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

export default function VMCPOAuthSetupCallbackPage() {
  const router = useRouter();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Processing OAuth setup callback...');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    handleCallback();
  }, []);

  const handleCallback = async () => {
    try {
      // Get URL parameters
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');
      const vmcpId = searchParams.get('vmcp_id');

      if (error) {
        setStatus('error');
        setError(errorDescription || error);
        setMessage('OAuth setup authorization failed');
        return;
      }

      if (!code || !state) {
        setStatus('error');
        setError('Missing required OAuth parameters');
        setMessage('Invalid callback request');
        return;
      }

      // The backend should handle the OAuth callback automatically
      // We just need to show success and close the window
      setStatus('success');
      setMessage('VMCP OAuth setup completed successfully!');

      // Close the window after a short delay
      setTimeout(() => {
        if (window.opener) {
          // If this window was opened by another window, close it
          window.close();
        } else {
          // Otherwise redirect to vmcp page
          router.push('/vmcp');
        }
      }, 2000);

    } catch (err) {
      console.error('OAuth setup callback error:', err);
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
      setMessage('Failed to process OAuth setup callback');
    }
  };

  const handleClose = () => {
    if (window.opener) {
      window.close();
    } else {
      router.push('/vmcp');
    }
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-white/10 backdrop-blur-lg border-white/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center space-x-2">
            {status === 'success' && <CheckCircle className="h-6 w-6 text-green-400" />}
            {status === 'error' && <XCircle className="h-6 w-6 text-red-400" />}
            {status === 'loading' && <Loader2 className="h-6 w-6 animate-spin text-blue-400" />}
            <span>
              {status === 'success' && 'VMCP Setup Successful'}
              {status === 'error' && 'VMCP Setup Failed'}
              {status === 'loading' && 'Processing VMCP Setup'}
            </span>
          </CardTitle>
          <CardDescription className="text-gray-300">
            {message}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status === 'error' && error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
              <p className="text-red-200 text-sm">{error}</p>
            </div>
          )}

          {status === 'success' && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
              <p className="text-green-200 text-sm">
                Your VMCP OAuth setup has been completed successfully. This window will close automatically.
              </p>
            </div>
          )}

          <Button 
            onClick={handleClose}
            className="w-full"
            variant={status === 'error' ? 'outline' : 'default'}
          >
            {status === 'error' ? 'Close' : 'Continue'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
