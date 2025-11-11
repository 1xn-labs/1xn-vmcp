
import React, { useState, useEffect, Suspense } from 'react';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/auth-context';
import { useGoogleAuth } from '@/hooks/useGoogleAuth';
import { GoogleAuthButton } from '@/components/ui/GoogleAuthButton';
import { ArrowRight, User } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

function LoginForm() {
  const router = useRouter();
  const [searchParams] = useSearchParams();

  // Check for register mode parameter early
  const registerMode = searchParams.get('register') === 'true' || searchParams.get('mode') === 'register';

  const [mode, setMode] = useState<'login' | 'register'>(registerMode ? 'register' : 'login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Register form state
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
  });
  const [passwordStrength, setPasswordStrength] = useState({
    score: 0,
    feedback: '',
    color: 'bg-slate-200',
  });
  const [passwordMatch, setPasswordMatch] = useState<boolean|null>(null);
  const [usernameError, setUsernameError] = useState<string>('');


  // OAuth parameters
  const clientId = searchParams.get('client_id');
  const redirectUri = searchParams.get('redirect_uri');
  const scope = searchParams.get('scope');
  const state = searchParams.get('state');
  const codeChallenge = searchParams.get('code_challenge');
  const codeChallengeMethod = searchParams.get('code_challenge_method');
  const clientName = searchParams.get('client_name');
  const clientDescription = searchParams.get('client_description');
  const clientUri = searchParams.get('client_uri');

  // vMCP parameters
  const vmcpName = searchParams.get('vmcp_name');
  const vmcpUsername = searchParams.get('vmcp_username');

  // Check if this is an OAuth authorization flow
  const isOAuthFlow = clientId && redirectUri;

  console.log('🚀 LoginForm initialized - OAuth flow:', { isOAuthFlow, clientId, redirectUri, vmcpName, vmcpUsername, registerMode, mode });

  const { signInWithGoogle, loading: googleLoading } = useGoogleAuth();
  const { login, user, isAuthenticated } = useAuth();

  // Register validation functions
  const validateUsername = (username: string) => {
    if (!username) {
      setUsernameError('Username is required');
      return false;
    }
    if (username.length < 3) {
      setUsernameError('Username must be at least 3 characters');
      return false;
    }
    if (username.length > 50) {
      setUsernameError('Username must be less than 50 characters');
      return false;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(username)) {
      setUsernameError('Username can only contain letters, numbers, and underscores');
      return false;
    }
    setUsernameError('');
    return true;
  };

  const checkPasswordStrength = (password: string) => {
    let score = 0;
    let feedback = '';
    let color = 'bg-slate-200';

    if (password.length >= 8) score += 1;
    if (password.match(/[a-z]+/)) score += 1;
    if (password.match(/[A-Z]+/)) score += 1;
    if (password.match(/[0-9]+/)) score += 1;
    if (password.match(/[$@#&!]+/)) score += 1;

    switch (score) {
      case 0:
      case 1:
        feedback = 'Weak';
        color = 'bg-red-500';
        break;
      case 2:
        feedback = 'Fair';
        color = 'bg-amber-500';
        break;
      case 3:
      case 4:
        feedback = 'Good';
        color = 'bg-emerald-500';
        break;
      case 5:
        feedback = 'Strong';
        color = 'bg-emerald-600';
        break;
    }

    setPasswordStrength({ score, feedback, color });
  };

  const handleRegisterChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));

    if (field === 'username') {
      validateUsername(value);
    }

    if (field === 'password') {
      checkPasswordStrength(value);
    }

    if (field === 'confirmPassword') {
      setPasswordMatch(formData.password === value);
    }
  };

  // State for OAuth client information
  const [clientInfo, setClientInfo] = useState<{
    client_name?: string;
    client_uri?: string;
    description?: string;
  } | null>(null);

  // Utility function to safely check if a string is a valid URL
  const isValidUrl = (urlString: string): boolean => {
    try {
      new URL(urlString);
      return true;
    } catch {
      return false;
    }
  };

  // Utility function to check if URL is valid for favicon fetching
  const isValidUrlForFavicon = (urlString: string): boolean => {
    try {
      const url = new URL(urlString);
      // Exclude localhost and local IPs from favicon fetching
      return url.hostname !== 'localhost' && !url.hostname.startsWith('127.') && !url.hostname.startsWith('192.168.') && !url.hostname.startsWith('10.');
    } catch {
      return false;
    }
  };

  // Fetch OAuth client information if in OAuth flow
  useEffect(() => {
    if (isOAuthFlow && clientId) {
      setClientInfo({
        client_name: clientName || `Client (${clientId})`,
        client_uri: clientUri || redirectUri,
        description: clientDescription && clientDescription !== 'None' ? clientDescription : 'wants to access your 1xN account'
      });
      console.log('Effect: Fetched OAuth client info:', { clientId, clientName, clientDescription, clientUri });
    }
  }, [isOAuthFlow, clientId, clientName, clientDescription, clientUri, redirectUri]);

  useEffect(() => {
    if (user && isAuthenticated && isOAuthFlow) {
      console.log('LoginForm: User already authenticated, handling OAuth flow...');
      handleAuthenticatedOAuthFlow();
    }
  }, [user, isAuthenticated, isOAuthFlow]);

  // Note: OAuth callback redirect is handled in auth-context.tsx after token storage

  const handleAuthenticatedOAuthFlow = async () => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      console.error('No access token available for authenticated user');
      return;
    }

    try {
      // OAuth authorization flow with existing access token
      const oauthData = {
        access_token: accessToken,
        client_id: clientId,
        redirect_uri: redirectUri,
        scope: scope || 'openid profile email mcp:read mcp:write',
        response_type: 'code',
        state,
        code_challenge: codeChallenge,
        code_challenge_method: codeChallengeMethod || 'S256'
      };

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      };
      if (vmcpName) headers['vmcp-name'] = vmcpName;
      if (vmcpUsername) headers['vmcp-username'] = vmcpUsername;

      console.log('Calling OAuth authorize with access token for authenticated user');
      const response = await fetch('/api/oauth/authorize', {
        method: 'POST',
        headers,
        body: JSON.stringify(oauthData)
      });

      const result = await response.json();

      if (response.ok && result.redirect_url) {
        // For OAuth flow, redirect to configuration page
        let configUrl;
        if (vmcpUsername) {
          configUrl = `/oauth/${vmcpName}/${vmcpUsername}/configure?redirect_url=${encodeURIComponent(result.redirect_url)}&auth_code=${result.auth_code || ''}&state=${state || ''}&user_id=${result.user_id || user?.id}&vmcp_username=${vmcpUsername}`;
        } else {
          configUrl = `/oauth/${vmcpName}/configure?redirect_url=${encodeURIComponent(result.redirect_url)}&auth_code=${result.auth_code || ''}&state=${state || ''}&user_id=${result.user_id || user?.id}`;
        }
        console.log('Redirecting to config URL:', configUrl);
        window.location.href = configUrl;
        return;
      } else {
        console.error('OAuth flow failed for authenticated user:', result);
        setError('Failed to process OAuth authorization. Please try again.');
      }
    } catch (err) {
      console.error('Error in authenticated OAuth flow:', err);
      setError('Error processing OAuth authorization. Please try again.');
    }
  };

  const getErrorMessage = (err: any): string => {
    // Handle network errors
    if (!navigator.onLine) {
      return 'No internet connection. Please check your network and try again.';
    }

    // Get error message from the error object
    let errorMessage = '';
    if (err instanceof Error) {
      errorMessage = err.message;
    } else if (typeof err === 'string') {
      errorMessage = err;
    } else if (err?.message) {
      errorMessage = err.message;
    } else if (err?.detail) {
      errorMessage = err.detail;
    } else {
      errorMessage = 'Login failed';
    }

    // Map specific error messages to user-friendly ones
    const lowerMessage = errorMessage.toLowerCase();

    if (lowerMessage.includes('invalid credentials') ||
      lowerMessage.includes('unauthorized') ||
      lowerMessage.includes('401') ||
      lowerMessage.includes('redirecting to login')) {
      return 'Invalid username/email or password. Please check your credentials and try again.';
    }

    if (lowerMessage.includes('account is disabled') ||
      lowerMessage.includes('account disabled')) {
      return 'Your account has been disabled. Please contact support for assistance.';
    }

    if (lowerMessage.includes('500') ||
      lowerMessage.includes('internal server error') ||
      lowerMessage.includes('server error')) {
      return 'Server error occurred. Please try again in a few moments.';
    }

    if (lowerMessage.includes('timeout') ||
      lowerMessage.includes('network')) {
      return 'Connection timeout. Please check your internet connection and try again.';
    }

    if (lowerMessage.includes('fetch') ||
      lowerMessage.includes('network error')) {
      return 'Unable to connect to the server. Please try again.';
    }

    // If it's a recognizable error message, return it as-is
    if (errorMessage.length > 0 && errorMessage !== 'Login failed') {
      return errorMessage;
    }

    // Default fallback
    return 'Login failed. Please try again or contact support if the problem persists.';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Clear previous messages
    setError('');
    setSuccess('');

    if (!username.trim() || !password.trim()) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      if (isOAuthFlow) {
        // OAuth authorization flow
        const oauthData = {
          username,
          password,
          client_id: clientId,
          redirect_uri: redirectUri,
          scope: scope || 'openid profile email mcp:read mcp:write',
          response_type: 'code',
          state,
          code_challenge: codeChallenge,
          code_challenge_method: codeChallengeMethod || 'S256'
        };

        const headers: Record<string, string> = {
          'Content-Type': 'application/json'
        };
        if (vmcpName) headers['vmcp-name'] = vmcpName;
        if (vmcpUsername) headers['vmcp-username'] = vmcpUsername;

        const response = await fetch('/api/oauth/authorize', {
          method: 'POST',
          headers,
          body: JSON.stringify(oauthData)
        });

        const result = await response.json();

        if (response.ok && result.redirect_url) {
          // For OAuth flow, redirect to configuration page
          let configUrl;
          if (vmcpUsername) {
            configUrl = `/oauth/${vmcpName}/${vmcpUsername}/configure?redirect_url=${encodeURIComponent(result.redirect_url)}&auth_code=${result.auth_code || ''}&state=${state || ''}&user_id=${result.user_id || ''}&vmcp_username=${vmcpUsername}`;
          } else {
            configUrl = `/oauth/${vmcpName}/configure?redirect_url=${encodeURIComponent(result.redirect_url)}&auth_code=${result.auth_code || ''}&state=${state || ''}&user_id=${result.user_id || ''}`;
          }
          window.location.href = configUrl;
          return;
        } else {
          const friendlyMessage = getErrorMessage(result);
          setError(friendlyMessage);
        }
      } else {
        // Standard login flow
        const result = await login(username, password);

        if (result.success) {
          // Redirect to the return URL or settings
          const redirectUrl = '/settings';
          router.push(redirectUrl);
          return;
        } else {
          const friendlyMessage = getErrorMessage(result.error);
          console.log('🚨 Displaying error message:', friendlyMessage);
          setError(friendlyMessage);
        }
      }
    } catch (err) {
      const friendlyMessage = getErrorMessage(err);
      console.log('🚨 Displaying error message:', friendlyMessage);
      setError(friendlyMessage);

      // Log the original error for debugging
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    try {
      if (isOAuthFlow) {
        // OAuth flow with Google
        const oauthParams = new URLSearchParams({
          provider: 'google',
          web_client_url: redirectUri || '',
          client_id: clientId || 'unknown-mcp-client',
          oauth_flow: 'true',
          auth_mode: 'signin',
          original_state: state || '',
          vmcp_name: vmcpName || '',
          vmcp_username: vmcpUsername || ''
        });

        await signInWithGoogle(false, redirectUri, undefined, oauthParams);  
      } else {
        // Standard Google sign-in
        await signInWithGoogle(false);
      }
    } catch (error) {
      setError('Google sign-in failed. Please try again.');
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.username.trim() || !formData.email.trim() || !formData.password.trim() || !formData.first_name.trim() || !formData.last_name.trim()) {
      setError('Please fill in all required fields');
      return;
    }

    if (!validateUsername(formData.username)) {
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    setLoading(true);
    try {
      // Create the account using the new API format
      const result = await apiClient.register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
        full_name: `${formData.first_name} ${formData.last_name}`.trim(),
      });

      if (result.success) {
        setSuccess('Account created successfully! Please check your email to verify your account.');

        // Switch to login mode after successful registration
        setTimeout(() => {
          setMode('login');
          setUsername(formData.username);
          setSuccess('Account created! You can now sign in.');
        }, 2000);
      } else {
        setError(result.error || 'Registration failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignUp = async () => {
    // Validate username before proceeding with Google sign-up
    if (!formData.username.trim()) {
      setError('Username is required for Google sign-up');
      return;
    }

    if (!validateUsername(formData.username)) {
      return;
    }

    try {
      // Store username for OAuth callback
      localStorage.setItem('google_signup_username', formData.username);

      if (isOAuthFlow) {
        // OAuth flow with Google sign-up
        const oauthParams = new URLSearchParams({
          provider: 'google',
          web_client_url: redirectUri || '',
          client_id: clientId || 'unknown-mcp-client',
          oauth_flow: 'true',
          auth_mode: 'signup',
          original_state: state || '',
          vmcp_name: vmcpName || '',
          vmcp_username: vmcpUsername || ''
        });

        await signInWithGoogle(true, redirectUri, formData.username, oauthParams);

      } else {
        // Standard Google sign-up
        await signInWithGoogle(true, undefined, formData.username, undefined);
      }
    } catch (err) {
      setError('Google sign-up failed. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/10 via-transparent to-background text-foreground overflow-hidden relative">
      {/* Simple primary glow */}
      {/* <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent"></div> */}

      {/* Main Container */}
      <div className="relative h-screen overflow-y-auto">
        <div className="flex items-center justify-center px-4 py-8 min-h-screen">
          <div className="w-full max-w-md">
            {/* Logo and title */}
            {!isOAuthFlow && (
              <div className="text-center mb-8">
              <div className="w-32 h-32 mx-auto mb-6 rounded-2xl overflow-hidden shadow-2xl shadow-violet-500/30">
                <img
                  src={`/app/1xn_logo.svg`}
                  alt="1xN Logo"
                  className="w-full h-full object-contain"
                />
              </div>
              <h1 className="text-3xl font-bold text-foreground mb-2">
                {isOAuthFlow ? '1XN' : 'Welcome Back'}
              </h1>
              <p className="text-muted-foreground">
                {isOAuthFlow ? 'MCP Server Management' : 'Sign in to your 1xN account'}
              </p>
            </div>
            )}

            {/* OAuth Client Connection - only show in OAuth flow */}
            {isOAuthFlow && clientInfo && (
              <div className="mb-6 p-6 bg-muted/50 rounded-lg border border-accent/70 shadow-sm">
                <div className="flex items-center justify-center gap-4">
                  {/* Client */}
                  <div className="flex flex-col items-center text-center">
                    <div className="w-12 h-12 bg-card border border-border rounded-lg flex items-center justify-center mb-2 relative">
                      {(() => {
                        // Try client_uri first, then fallback to redirectUri
                        const faviconUrl = (clientInfo.client_uri && isValidUrlForFavicon(clientInfo.client_uri))
                          ? clientInfo.client_uri
                          : (redirectUri && isValidUrlForFavicon(redirectUri))
                            ? redirectUri
                            : null;

                        return faviconUrl ? (
                          <>
                            <img
                              src={`https://www.google.com/s2/favicons?domain=${new URL(faviconUrl).hostname}&sz=32`}
                              alt="Client favicon"
                              className="w-6 h-6"
                              onError={(e) => {
                                const img = e.currentTarget;
                                const fallback = img.nextElementSibling as HTMLElement;
                                img.style.display = 'none';
                                if (fallback) fallback.style.display = 'flex';
                              }}
                            />
                            <User className="w-6 h-6 text-muted-foreground hidden" />
                          </>
                        ) : (
                          <User className="w-6 h-6 text-muted-foreground" />
                        );
                      })()}
                    </div>
                    <div className="font-medium text-sm text-foreground">
                      {clientInfo.client_name}
                    </div>
                    {clientInfo.client_uri && isValidUrl(clientInfo.client_uri) && (
                      <div className="text-sm text-muted-foreground">
                        {new URL(clientInfo.client_uri).hostname}
                      </div>
                    )}
                  </div>

                  {/* Connection Arrow */}
                  <div className="flex flex-col items-center">
                    <ArrowRight className="w-6 h-6 text-primary animate-pulse" />
                  </div>

                  {/* 1xN */}
                  <div className="flex flex-col items-center text-center">
                    <div className="w-12 h-12 bg-primary/10 border border-primary/20 rounded-lg flex items-center justify-center mb-2">
                      <img
                        src={`/app/1xn_logo.svg`}
                        alt="1xN Logo"
                        className="w-8 h-8"
                      />
                    </div>
                    <div className="font-medium text-sm text-foreground">
                      1xN
                    </div>
                    <div className="text-sm text-muted-foreground font-bold">
                       {vmcpUsername !== 'private'
                      ? `vMCP: ${vmcpUsername}'s ${vmcpName}`
                      : `vMCP: ${vmcpName}`
                    }
                    </div>
                  </div>
                </div>

                {clientInfo.description && clientInfo.description !== 'wants to access your 1xN account' && (
                  <div className="mt-4 text-sm text-muted-foreground text-center">
                    {clientInfo.description}
                  </div>
                )}

                {scope && (
                  <div className="mt-3 text-xs text-muted-foreground text-center">
                    <strong>Scopes:</strong> {scope}
                  </div>
                )}
              </div>
            )}

            {/* Mode Toggle */}
            <div className="mb-6 flex bg-muted/50 rounded-lg p-1 border">
              <button
                onClick={() => {
                  setMode('login');
                  setError('');
                  setSuccess('');
                }}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                  mode === 'login'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Sign In
              </button>
              <button
                onClick={() => {
                  setMode('register');
                  setError('');
                  setSuccess('');
                }}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                  mode === 'register'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Create Account
              </button>
            </div>

            {/* Form Container */}
            <div className="bg-card border border-border rounded-2xl shadow-lg p-8">
              {/* Already authenticated message for OAuth flow */}
              {isOAuthFlow && user && isAuthenticated && (
                <div className="mb-6 p-4 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800">
                  <div className="flex items-center">
                    <div className="shrink-0">
                      <svg className="h-5 w-5 text-blue-600" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.236 4.53L7.53 10.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-blue-900 dark:text-blue-100">
                        Already signed in as <strong>{user.username}</strong>. Processing OAuth authorization...
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {/* Error Message */}
              {error && (
                <div className="mb-6 p-4 rounded-lg bg-destructive/10 border border-destructive/30 backdrop-blur-sm">
                  <div className="flex items-center">
                    <div className="shrink-0">
                      <svg className="h-5 w-5 text-destructive" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-destructive-foreground">{error}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Success Message */}
              {success && (
                <div className="mb-6 p-4 rounded-lg bg-green-500/10 border border-green-500/30 backdrop-blur-sm">
                  <div className="flex items-center">
                    <div className="shrink-0">
                      <svg className="h-5 w-5 text-green-600" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.236 4.53L7.53 10.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-green-600">{success}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Login Form */}
              {mode === 'login' && !(isOAuthFlow && user && isAuthenticated) && (
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div>
                    <label htmlFor="username" className="block text-sm font-medium text-foreground mb-2">
                      Username or Email
                    </label>
                    <Input
                      id="username"
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Enter your username or email"
                      required
                      autoComplete="username"
                      className="bg-background border-input text-foreground placeholder-muted-foreground focus:border-ring focus:ring-ring/20"
                    />
                  </div>

                  <div>
                    <label htmlFor="password" className="block text-sm font-medium text-foreground mb-2">
                      Password
                    </label>
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      required
                      autoComplete="current-password"
                      className="bg-background border-input text-foreground placeholder-muted-foreground focus:border-ring focus:ring-ring/20"
                    />
                  </div>

                  <Button
                    type="submit"
                    className="w-full bg-gradient-to-r from-primary to-primary/90 hover:from-primary hover:to-primary/90 text-primary-foreground font-semibold py-3 px-6 rounded-lg shadow-lg hover:shadow-primary/25 transition-all duration-300 hover:scale-105 border-0"
                  >
                    {loading ? 'Signing In...' : 'Sign In'}
                  </Button>
                </form>
              )}

              {/* Register Form */}
              {mode === 'register' && !(isOAuthFlow && user && isAuthenticated) && (
                <div className="space-y-6">
                  {/* Quick Google Sign-up Section */}
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="quick-username" className="block text-sm font-medium text-foreground mb-2">
                        Username *
                      </label>
                      <Input
                        id="quick-username"
                        type="text"
                        value={formData.username}
                        onChange={(e) => handleRegisterChange('username', e.target.value)}
                        placeholder="Enter your username"
                        required
                        autoComplete="username"
                        className={usernameError ? 'border-red-500' : ''}
                      />
                      {usernameError && (
                        <p className="mt-1 text-xs text-red-500">{usernameError}</p>
                      )}
                      <p className="mt-1 text-xs text-muted-foreground">
                        3-50 characters, letters, numbers, and underscores only
                      </p>
                    </div>

                    <GoogleAuthButton
                      loading={googleLoading}
                      onClick={handleGoogleSignUp}
                      mode="register"
                      disabled={!formData.username.trim() || !!usernameError}
                    />
                  </div>

                  {/* Divider */}
                  <div className="my-6">
                    <div className="relative">
                      <div className="absolute inset-0 flex items-center">
                        <div className="w-full border-t border-border/30"></div>
                      </div>
                      <div className="relative flex justify-center text-sm">
                        <span className="px-3 bg-card/50 text-muted-foreground font-medium">or</span>
                      </div>
                    </div>
                  </div>

                  {/* Full Registration Form */}
                  <form onSubmit={handleRegisterSubmit} className="space-y-6">
                    <div>
                      <label htmlFor="reg-username" className="block text-sm font-medium text-foreground mb-2">
                        Username *
                      </label>
                      <Input
                        id="reg-username"
                        type="text"
                        value={formData.username}
                        onChange={(e) => handleRegisterChange('username', e.target.value)}
                        placeholder="Enter your username"
                        required
                        autoComplete="username"
                        className={usernameError ? 'border-red-500' : ''}
                      />
                      {usernameError && (
                        <p className="mt-1 text-xs text-red-500">{usernameError}</p>
                      )}
                    </div>

                    <div>
                      <label htmlFor="email" className="block text-sm font-medium text-foreground mb-2">
                        Email *
                      </label>
                      <Input
                        id="email"
                        type="email"
                        value={formData.email}
                        onChange={(e) => handleRegisterChange('email', e.target.value)}
                        placeholder="Enter your email"
                        required
                        autoComplete="email"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="first_name" className="block text-sm font-medium text-foreground mb-2">
                          First Name *
                        </label>
                        <Input
                          id="first_name"
                          type="text"
                          value={formData.first_name}
                          onChange={(e) => handleRegisterChange('first_name', e.target.value)}
                          placeholder="First name"
                          required
                          autoComplete="given-name"
                        />
                      </div>

                      <div>
                        <label htmlFor="last_name" className="block text-sm font-medium text-foreground mb-2">
                          Last Name *
                        </label>
                        <Input
                          id="last_name"
                          type="text"
                          value={formData.last_name}
                          onChange={(e) => handleRegisterChange('last_name', e.target.value)}
                          placeholder="Last name"
                          required
                          autoComplete="family-name"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="reg-password" className="block text-sm font-medium text-foreground mb-2">
                          Password *
                        </label>
                        <Input
                          id="reg-password"
                          type="password"
                          value={formData.password}
                          onChange={(e) => handleRegisterChange('password', e.target.value)}
                          placeholder="Enter your password"
                          required
                          autoComplete="new-password"
                        />

                        {/* Password strength indicator */}
                        {formData.password && (
                          <div className="mt-2">
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className={`h-full transition-all duration-300 ${passwordStrength.color}`}
                                style={{ width: `${(passwordStrength.score / 5) * 100}%` }}
                              />
                            </div>
                            <p className="mt-1 text-xs text-foreground">
                              Strength: {passwordStrength.feedback}
                            </p>
                          </div>
                        )}
                      </div>

                      <div>
                        <label htmlFor="confirmPassword" className="block text-sm font-medium text-foreground mb-2">
                          Confirm Password *
                        </label>
                        <Input
                          id="confirmPassword"
                          type="password"
                          value={formData.confirmPassword}
                          onChange={(e) => handleRegisterChange('confirmPassword', e.target.value)}
                          placeholder="Confirm your password"
                          required
                          autoComplete="new-password"
                        />
                        <p className={`mt-1 text-xs ${passwordMatch || passwordMatch === null ? 'text-muted-foreground' : 'text-amber-500'}`}>
                          {passwordMatch || passwordMatch === null ? 'Must match your password' : 'Passwords dont match'}
                        </p>
                      </div>
                    </div>

                    <Button
                      type="submit"
                      disabled={!passwordMatch || !!usernameError || loading || googleLoading}
                      className="w-full bg-gradient-to-r from-primary to-primary/90 hover:from-primary hover:to-primary/90 text-primary-foreground font-semibold py-3 px-6 rounded-lg shadow-lg hover:shadow-primary/25 transition-all duration-300 hover:scale-105 border-0"
                    >
                      {loading ? 'Creating Account...' : 'Create Account'}
                    </Button>
                  </form>
                </div>
              )}

              {/* Social Login Section - only for login mode */}
              {mode === 'login' && !(isOAuthFlow && user && isAuthenticated) && (
                <div className="mt-6">
                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-border/30"></div>
                    </div>
                    <div className="relative flex justify-center text-sm">
                      <span className="px-3 bg-card/50 text-muted-foreground font-medium">or</span>
                    </div>
                  </div>

                  <div className="mt-6">
                    <GoogleAuthButton
                      loading={googleLoading}
                      onClick={handleGoogleSignIn}
                      mode="login"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 text-foreground overflow-hidden relative">
        {/* Simple primary glow */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent"></div>
        <div className="relative z-10 h-screen overflow-y-auto flex items-center justify-center">
          <div className="text-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
} 
      