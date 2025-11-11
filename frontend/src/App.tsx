import { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@/contexts/theme-context';
import { AuthProvider } from '@/contexts/auth-context';
import AuthGuard from '@/components/auth/AuthGuard';

// Lazy load pages for better performance
const LoginPage = lazy(() => import('@/pages/LoginPage'));
const ServersPage = lazy(() => import('@/pages/ServersPage'));
const AddServerPage = lazy(() => import('@/pages/AddServerPage'));
const EditServerPage = lazy(() => import('@/pages/EditServerPage'));
const TestServerPage = lazy(() => import('@/pages/TestServerPage'));
const VMCPListPage = lazy(() => import('@/pages/VMCPListPage'));
const VMCPDetailsPage = lazy(() => import('@/pages/VMCPDetailsPage'));
const VMCPInstallPage = lazy(() => import('@/pages/VMCPInstallPage'));
const VMCPSharePage = lazy(() => import('@/pages/VMCPSharePage'));
const DiscoverPage = lazy(() => import('@/pages/DiscoverPage'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));
const StatsPage = lazy(() => import('@/pages/StatsPage'));
const OAuthAuthorizePage = lazy(() => import('@/pages/OAuthAuthorizePage'));
const OAuthCallbackSuccessPage = lazy(() => import('@/pages/OAuthCallbackSuccessPage'));
const OAuthCallbackMCPPage = lazy(() => import('@/pages/OAuthCallbackMCPPage'));
const OAuthSetupConfigurePage = lazy(() => import('@/pages/OAuthSetupConfigurePage'));
const OAuthSetupCallbackPage = lazy(() => import('@/pages/OAuthSetupCallbackPage'));

// Loading component
function LoadingFallback() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}

function App() {
  const authDisabled = import.meta.env.VITE_VMCP_OSS_BUILD === 'true';

  return (
    <ThemeProvider>
      <AuthProvider>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />


            {/* OAuth routes */}
            <Route path="/oauth/authorize" element={<OAuthAuthorizePage />} />
            <Route path="/oauth/callback/success" element={<OAuthCallbackSuccessPage />} />
            <Route path="/oauth/callback/mcp" element={<OAuthCallbackMCPPage />} />
            <Route path="/oauth_setup/:vmcp_name/configure" element={<OAuthSetupConfigurePage />} />
            <Route path="/oauth_setup/:vmcp_name/callback" element={<OAuthSetupCallbackPage />} />

            {/* Root path - redirect to /vmcp */}
            <Route
              path="/"
              element={<Navigate to="/vmcp" replace />}
            />

            {/* Protected routes */}
            <Route path="/servers" element={<AuthGuard><ServersPage /></AuthGuard>} />
            <Route path="/servers/add" element={<AuthGuard><AddServerPage /></AuthGuard>} />
            <Route path="/servers/:name/edit" element={<AuthGuard><EditServerPage /></AuthGuard>} />
            <Route path="/servers/:name/:id/test" element={<AuthGuard><TestServerPage /></AuthGuard>} />
            <Route path="/vmcp" element={<AuthGuard><VMCPListPage /></AuthGuard>} />
            <Route path="/vmcp/:id" element={<AuthGuard><VMCPDetailsPage /></AuthGuard>} />
            <Route path="/vmcp/install/:vmcp_id/:vmcp_type" element={<AuthGuard><VMCPInstallPage /></AuthGuard>} />
            <Route path="/vmcp/share/:vmcp_id" element={<AuthGuard><VMCPSharePage /></AuthGuard>} />
            <Route path="/discover" element={<AuthGuard><DiscoverPage /></AuthGuard>} />
            <Route path="/settings" element={<AuthGuard><SettingsPage /></AuthGuard>} />
            <Route path="/stats" element={<AuthGuard><StatsPage /></AuthGuard>} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
