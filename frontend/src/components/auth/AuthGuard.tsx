
import { useAuth } from '@/contexts/auth-context';
import { useSearchParams, useLocation } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { useEffect } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { AppProvider } from '@/contexts/AppProvider';

interface AuthGuardProps {
  children: React.ReactNode;
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const authDisabled = import.meta.env.VITE_VMCP_OSS_BUILD === 'true';

  // If auth is disabled (OSS build), bypass all auth checks
  if (authDisabled) {
    console.log('🔓 AuthGuard: Auth disabled for OSS build, bypassing auth checks');
    return (
      <AppProvider>
        <MainLayout>
          {children}
        </MainLayout>
      </AppProvider>
    );
  }

  const { user, loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const { pathname } = useLocation();
  const [urlParams] = useSearchParams();

  const isVmcpOauth = urlParams.get('client_id') !== null;

  console.log('🔒 AuthGuard initialized');

  // Define public pages that don't require authentication
  const publicPages = ['/login'];
  
  // Check if current page is an OAuth setup page (dynamic route)
  const isOAuthSetupPage = pathname.startsWith('/oauth_setup/') || isVmcpOauth
  
  // Check if current page is public
  const isPublicPage = publicPages.some(page => pathname === page) || isOAuthSetupPage;

  useEffect(() => {
    if (!loading) {
      // Special case: Root path "/" should always show landing page for unauthenticated users
      if (pathname === '/' && !isAuthenticated) {
        // Do nothing - let the page render the landing page
        console.log('AuthGuard: User not authenticated on root path, showing landing page');
        return;
      }
      
      // Check if we're processing OAuth callback (has access_token in URL)
      const isProcessingOAuth = urlParams.has('access_token') && urlParams.has('refresh_token');
      
      if (!isAuthenticated && !isPublicPage) {
        // Redirect to login if not authenticated and trying to access protected page
        console.log('AuthGuard: User not authenticated, redirecting to /login');
        router.push('/login');
      } else if (isAuthenticated && isPublicPage) {
         if (isOAuthSetupPage) {
            console.log('AuthGuard: vMCP OAuth detected, allowing access to OAuth setup page');
            return; 
          } else if (pathname === '/') {
            // Allow authenticated users to stay on landing page
            console.log('AuthGuard: User authenticated on root path, allowing access to landing page');
            return;
          } else if (isProcessingOAuth) {
            // Don't redirect if we're processing OAuth callback - let the auth context handle it
            console.log('AuthGuard: OAuth callback in progress, skipping redirect');
            return;
          } else {
            // Redirect authenticated users from other public pages to dashboard
            console.log('AuthGuard: User authenticated, redirecting to /vmcp');
            router.push('/vmcp');
          }
      }
    }
  }, [user, loading, isAuthenticated, router, pathname, isPublicPage, isOAuthSetupPage, urlParams]);

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"/>
          {/* <p className="text-muted-foreground">Auth...</p> */}
        </div>
      </div>
    );
  }

  // Special case: Root path should always render for unauthenticated users
  if (pathname === '/') {
    return <>{children}</>;
  }

  // Allow access to other public pages without authentication
  if (isPublicPage) {
    return <>{children}</>;
  }

  // Require authentication for protected pages
  if (!isAuthenticated) {
    return null; // Will redirect to login
  }

  return (
    <AppProvider>
      <MainLayout>
        {children}
      </MainLayout>
    </AppProvider>
  ) ;
}
