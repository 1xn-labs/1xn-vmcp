
import React, { useState, useEffect } from 'react';
import { useRouter } from '@/hooks/useRouter';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/contexts/auth-context';
import { useTheme } from '@/contexts/theme-context';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { User, Shield, Settings, Key, CheckCircle, AlertCircle, Clock, Calendar } from 'lucide-react';

export default function SettingsPage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const { theme } = useTheme();
  const [accessToken, setAccessToken] = useState<string>('');

  useEffect(() => {
    // Redirect to login if not authenticated and not loading
    // if (!authLoading && !isAuthenticated) {
    //   router.push('/login');
    //   return;
    // }

    // Get access token from localStorage for session info display
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token') || '';
      setAccessToken(token);
    }
  // }, [authLoading, isAuthenticated, router]);
}, []);

  if (authLoading) {
    return (
      <div className="min-h-screen text-foreground flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // The AuthGuard ensures this component only renders for authenticated users
  // if (!user || !isAuthenticated) {
  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">Manage your account settings and preferences.</p>
        </div>

        {/* User Profile Header */}
        <Card className="mb-8 flex flex-row items-center">
          <CardContent className="pt-6 flex-1">
            <div className="flex-1 items-center space-x-6">
              <Avatar className="h-16 w-16">
                {user.photo_url ? (
                  <AvatarImage 
                    src={user.photo_url} 
                    alt={`${user.full_name}'s profile picture`}
                  />
                ) : null}
                <AvatarFallback className="text-xl font-bold bg-primary text-primary-foreground">
                  {user.first_name?.[0]}{user.last_name?.[0]}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <h2 className="text-2xl font-bold">{user.full_name}</h2>
                <p className="text-muted-foreground mb-3">{user.email}</p>
                <div className="flex items-center gap-2">
                  <Badge variant={user.is_verified ? "default" : "secondary"} className="gap-1">
                    {user.is_verified ? (
                      <CheckCircle className="h-3 w-3" />
                    ) : (
                      <AlertCircle className="h-3 w-3" />
                    )}
                    {user.is_verified ? 'Verified' : 'Pending Verification'}
                  </Badge>
                  <Badge variant={user.is_active ? "default" : "destructive"}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </div>
            </div>
          </CardContent>
          <CardContent>
            <div className="flex flex-col items-center justify-between p-4 border rounded-md">
                <p className="font-medium">Theme Settings</p>
                <p className="text-xs text-muted-foreground">
                  Mode: {theme.mode} • Palette: {theme.palette}
                </p>
              <ThemeToggle />
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Account Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Account Information
              </CardTitle>
              <CardDescription>
                Your account details and membership information.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <div className="flex items-center justify-between p-3 bg-muted/50 rounded-md">
                  <span className="text-sm text-muted-foreground">User Name</span>
                  <code className="font-mono text-sm">{user.username}</code>
                </div>
              </div> 

              <div className="space-y-1">
                <div className="flex items-center justify-between p-3 bg-muted/50 rounded-md">
                  <span className="text-sm text-muted-foreground">ID</span>
                  <code className="font-mono text-sm">{user.id}</code>
                </div>
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium">Email</Label>
                <Input value={user.email} disabled />
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium">Full Name</Label>
                <Input value={user.full_name} disabled />
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium">Account Status</Label>
                <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-md">
                  {user.is_active ? (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-red-600" />
                  )}
                  <span className={user.is_active ? 'text-green-600' : 'text-red-600'}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  Member Since
                </Label>
                <div className="p-3 bg-muted/50 rounded-md">
                  <span className="text-sm">
                    {new Date(user.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium flex items-center gap-1">
                  <Clock className="h-4 w-4" />
                  Last Login
                </Label>
                <div className="p-3 bg-muted/50 rounded-md">
                  <span className="text-sm">
                    {user.last_login 
                      ? new Date(user.last_login).toLocaleDateString()
                      : 'First time'
                    }
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Session Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                Session Information
              </CardTitle>
              <CardDescription>
                Current session details and authentication status.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label className="text-sm font-medium">Access Token</Label>
                <div className="p-3 bg-muted/50 rounded-md">
                  <code className="text-xs text-muted-foreground">
                    {accessToken ? `${accessToken.substring(0, 20)}...` : 'Not available'}
                  </code>
                </div>
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium">Token Type</Label>
                <Input value="Bearer" disabled />
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium">Client</Label>
                <Input value="web-client" disabled />
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium">Active Sessions</Label>
                <div className="flex items-center justify-between p-3 bg-muted/50 rounded-md">
                  <span className="text-sm text-muted-foreground">Sessions</span>
                  <Badge variant="outline">1</Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Platform Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                Platform Settings
              </CardTitle>
              <CardDescription>
                Application configuration and theme preferences.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label className="text-sm font-medium">MCP Server URL</Label>
                <Input 
                  value={import.meta.env.VITE_MCP_SERVER_URL || 'Not configured'}
                  disabled 
                />
              </div>
              
              <div className="space-y-1">
                <Label className="text-sm font-medium">Entity String</Label>
                <Input 
                  value={import.meta.env.VITE_ENTITY_STRING || 'Not configured'}
                  disabled 
                />
              </div>
              
              <Separator />
              
              <div className="space-y-3">
                <Label className="text-sm font-medium">Theme & Appearance</Label>
                <div className="flex items-center justify-between p-4 border rounded-md">
                  <div>
                    <p className="font-medium">Theme Settings</p>
                    <p className="text-xs text-muted-foreground">
                      Mode: {theme.mode} • Palette: {theme.palette}
                    </p>
                  </div>
                  <ThemeToggle />
                </div>
                <p className="text-xs text-muted-foreground">
                  Theme settings apply globally across the entire application
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Security Features */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-primary">
                <Shield className="h-5 w-5" />
                Security Features
              </CardTitle>
              <CardDescription> 
                Active security measures protecting your account.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 bg-background border border-accent/20 rounded-md">
                  <CheckCircle className="h-4 w-4 text-accent" />
                  <span className="text-sm">JWT Token Authentication</span>
                </div>
                <div className="flex items-center gap-3 p-3 bg-accent-500/10 border border-accent-500/20 rounded-md">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-sm text-green-700 dark:text-green-400">Session Tracking</span>
                </div>
                <div className="flex items-center gap-3 p-3 bg-accent-500/10 border border-accent-500/20 rounded-md">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-sm text-green-700 dark:text-green-400">Secure Password Hashing</span>
                </div>
                <div className="flex items-center gap-3 p-3 bg-accent-500/10 border border-accent-500/20 rounded-md">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-sm text-green-700 dark:text-green-400">OAuth Integration</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
  );
}